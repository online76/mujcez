"""Koordinátor: stahuje data z Můj ČEZ a udržuje přihlášení."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MujCezApiError, MujCezAuthError, MujCezClient
from .const import CONF_REFRESH_TOKEN, DATA_INTERVAL_H, DOMAIN, TOKEN_INTERVAL_MIN
from .parser import parse

_LOGGER = logging.getLogger(__name__)


class MujCezCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Data všech odběrných míst účtu, klíčem je EAN/EIC."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=DATA_INTERVAL_H))
        self.entry = entry
        self.client = MujCezClient(
            async_get_clientsession(hass), entry.data[CONF_REFRESH_TOKEN], on_token=self._save_token
        )
        self._unsub = None

    @callback
    def _save_token(self, token: str) -> None:
        self.hass.config_entries.async_update_entry(self.entry, data={**self.entry.data, CONF_REFRESH_TOKEN: token})

    @callback
    def start_keepalive(self) -> None:
        """Refresh token se obnovuje každých 10 min, aby přihlášení nevypršelo."""

        async def _tick(_now) -> None:
            try:
                await self.client.refresh()
            except MujCezAuthError:
                _LOGGER.warning("Můj ČEZ: přihlášení vypršelo, je potřeba se znovu přihlásit")
                self.entry.async_start_reauth(self.hass)
            except MujCezApiError as err:
                _LOGGER.debug("Můj ČEZ: obnovení tokenu se nepovedlo: %s", err)

        self._unsub = async_track_time_interval(self.hass, _tick, timedelta(minutes=TOKEN_INTERVAL_MIN))

    @callback
    def stop_keepalive(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            raw = await self.client.fetch_all()
        except MujCezAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MujCezApiError as err:
            raise UpdateFailed(str(err)) from err
        data = await self.hass.async_add_executor_job(parse, raw)
        if not data:
            raise UpdateFailed("Portál nevrátil žádná odběrná místa")
        return data
