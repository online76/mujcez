"""Přihlášení k Můj ČEZ: odkaz na přihlášení + vložení adresy, na kterou portál přesměruje."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import secrets
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector as sel

from .api import (
    MujCezApiError,
    MujCezAuthError,
    MujCezClient,
    authorize_url,
    exchange_code,
    extract_code,
    new_device_id,
    new_pkce,
)
from .const import CONF_DEVICE_ID, CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCHEMA = vol.Schema(
    {vol.Required("callback_url"): sel.TextSelector(sel.TextSelectorConfig(multiline=True))}
)


class MujCezConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._verifier, self._challenge = new_pkce()
        self._device = new_device_id()
        self._state = secrets.token_urlsafe(8)

    def _form(self, step_id: str, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        return self.async_show_form(
            step_id=step_id,
            data_schema=SCHEMA,
            errors=errors or {},
            description_placeholders={"url": authorize_url(self._challenge, self._device, self._state)},
        )

    async def _login(self, user_input: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, str]]:
        try:
            code = extract_code(user_input["callback_url"])
        except ValueError:
            return None, {"base": "no_code"}
        session = async_get_clientsession(self.hass)
        try:
            tokens = await exchange_code(session, code, self._verifier, self._device)
            client = MujCezClient(session, tokens["refresh_token"])
            client.set_access_token(tokens["access_token"], tokens.get("expires_in", 900))
            info = await client.token_data()
        except MujCezAuthError:
            return None, {"base": "invalid_code"}
        except (MujCezApiError, KeyError) as err:
            _LOGGER.warning("Můj ČEZ: přihlášení selhalo: %s", err)
            return None, {"base": "cannot_connect"}
        return {
            "refresh_token": client.refresh_token,
            "user": info.get("partnerIdCol") or info.get("email") or "",
            "email": info.get("email") or "",
            "name": " ".join(x for x in (info.get("individualFirstName"), info.get("individualSurname")) if x),
        }, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            res, errors = await self._login(user_input)
            if res:
                await self.async_set_unique_id(res["user"].lower() or None)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Můj ČEZ – {res['name'] or res['email']}",
                    data={CONF_REFRESH_TOKEN: res["refresh_token"], CONF_DEVICE_ID: self._device, "email": res["email"]},
                )
            return self._form("user", errors)
        return self._form("user")

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            res, errors = await self._login(user_input)
            if res:
                entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_REFRESH_TOKEN: res["refresh_token"], CONF_DEVICE_ID: self._device},
                )
            return self._form("reauth_confirm", errors)
        return self._form("reauth_confirm")
