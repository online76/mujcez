"""Klient portálu Můj ČEZ (muj.cez.cz).

Přihlášení: OAuth2 authorization code + PKCE přes auth.cez.cz (stejně jako webový portál).
Integrace nikdy nezná heslo – uživatel se přihlásí v prohlížeči a vloží adresu, na kterou ho
portál přesměruje. Dál se používá refresh token, který se při každém obnovení mění.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import date, timedelta
import hashlib
import logging
import secrets
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp

from .const import API_URL, AUTHORIZE_URL, CLIENT_ID, REDIRECT_URI, TOKEN_URL

_LOGGER = logging.getLogger(__name__)


class MujCezAuthError(Exception):
    """Přihlášení neplatí – je potřeba se znovu přihlásit."""


class MujCezApiError(Exception):
    """Chyba komunikace s portálem."""


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def new_pkce() -> tuple[str, str]:
    verifier = _b64u(secrets.token_bytes(32))
    challenge = _b64u(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def new_device_id() -> str:
    return "ha" + secrets.token_hex(5)


def scope(device_id: str) -> str:
    return f"openid device_{device_id}"


def authorize_url(challenge: str, device_id: str, state: str) -> str:
    return AUTHORIZE_URL + "?" + urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": scope(device_id),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )


def extract_code(text: str) -> str:
    """Z vložené adresy (nebo samotného kódu) vytáhne autorizační kód."""
    text = (text or "").strip()
    if "code=" in text:
        parsed = urlparse(text)
        for part in (parsed.query, parsed.fragment):
            code = parse_qs(part).get("code")
            if code:
                return code[0]
    if text and "/" not in text and " " not in text and len(text) >= 16:
        return text
    raise ValueError("no_code")


async def _token_request(session: aiohttp.ClientSession, data: dict[str, str]) -> dict[str, Any]:
    try:
        async with session.post(
            TOKEN_URL,
            data=data,
            headers={"Accept": "application/json"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status in (400, 401) or (isinstance(body, dict) and body.get("error")):
                raise MujCezAuthError(f"{resp.status}: {body}")
            resp.raise_for_status()
            return body
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        raise MujCezApiError(str(err)) from err


async def exchange_code(
    session: aiohttp.ClientSession, code: str, verifier: str, device_id: str
) -> dict[str, Any]:
    return await _token_request(
        session,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": verifier,
            "scope": scope(device_id),
        },
    )


class MujCezClient:
    """Volání API portálu s automatickým obnovováním tokenu."""

    def __init__(self, session: aiohttp.ClientSession, refresh_token: str, on_token=None) -> None:
        self._session = session
        self.refresh_token = refresh_token
        self._access_token: str | None = None
        self._expires = 0.0
        self._lock = asyncio.Lock()
        self._on_token = on_token  # callback(refresh_token) – uložení nového refresh tokenu

    def set_access_token(self, token: str, expires_in: int = 900) -> None:
        self._access_token = token
        self._expires = time.monotonic() + int(expires_in) - 60

    async def refresh(self) -> None:
        async with self._lock:
            body = await _token_request(
                self._session,
                {"grant_type": "refresh_token", "refresh_token": self.refresh_token, "client_id": CLIENT_ID},
            )
            self._access_token = body["access_token"]
            self._expires = time.monotonic() + int(body.get("expires_in", 900)) - 60
            new_rt = body.get("refresh_token")
            if new_rt and new_rt != self.refresh_token:
                self.refresh_token = new_rt
                if self._on_token:
                    self._on_token(new_rt)

    async def _token(self) -> str:
        if not self._access_token or time.monotonic() >= self._expires:
            await self.refresh()
        return self._access_token  # type: ignore[return-value]

    async def get(self, path: str, *, optional: bool = False) -> Any:
        for attempt in (1, 2):
            token = await self._token()
            try:
                async with self._session.get(
                    API_URL + path,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 401 and attempt == 1:
                        self._access_token = None
                        continue
                    if resp.status == 401:
                        raise MujCezAuthError("401")
                    if resp.status >= 400:
                        if optional:
                            _LOGGER.debug("Můj ČEZ %s -> %s", path, resp.status)
                            return None
                        raise MujCezApiError(f"{path}: HTTP {resp.status}")
                    if resp.status == 204:
                        return None
                    return await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                if optional:
                    return None
                raise MujCezApiError(f"{path}: {err}") from err
        return None

    async def token_data(self) -> dict[str, Any]:
        data = await self.get("/user/token-data")
        return (data or {}).get("tokenData", data or {})

    async def fetch_all(self) -> dict[str, Any]:
        """Stáhne všechna odběrná místa a k nim detail, spotřebu, odečty, zálohy a doklady."""
        today = date.today()
        points = await self.get("/supply-points/RetrieveSupplyPoints?loadAdvancePaymentInfo=true") or []
        billings = await self.get(
            f"/billings/extended?dateFrom={(today - timedelta(days=3 * 365)).isoformat()}", optional=True
        ) or []

        async def one(sp: dict[str, Any]) -> dict[str, Any]:
            uid = sp["supplyPointUniqueId"]
            code = sp["supplyPointCode"]
            cp = sp.get("consumptionPlaceIdIsu", "")
            detail, year, month, readings, advance = await asyncio.gather(
                self.get(f"/supply-points/{uid}/ReadSupplyPointDetail", optional=True),
                self.get(f"/supply-points/{uid}/ReadConsumptionHistory?aggregation=year", optional=True),
                self.get(f"/supply-points/{uid}/ReadConsumptionHistory?aggregation=month", optional=True),
                self.get(
                    f"/self-meter-reading?consumptionPlaceIdIsu={cp}"
                    f"&meterReadingRequestRegisterDate={today.isoformat()}&supplyPointCode={code}",
                    optional=True,
                ),
                self.get(f"/advance-payments/{uid}/settings", optional=True),
            )
            return {
                "point": sp,
                "detail": detail or {},
                "year": year or [],
                "month": month or [],
                "readings": readings or [],
                "advance": advance or {},
            }

        raw = await asyncio.gather(*(one(sp) for sp in points))
        return {"points": raw, "billings": billings if isinstance(billings, list) else []}
