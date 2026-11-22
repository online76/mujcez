"""Můj ČEZ – odběrná místa elektřiny a plynu z portálu muj.cez.cz."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import CARD_URL, DOMAIN, PLATFORMS, VERSION
from .coordinator import MujCezCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MujCezConfigEntry = ConfigEntry[MujCezCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Zpřístupní kartu custom:mujcez-card (bez ruční registrace zdroje)."""
    card = Path(__file__).parent / "www" / "mujcez-card.js"
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(card), False)])
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MujCezConfigEntry) -> bool:
    coordinator = MujCezCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    coordinator.start_keepalive()
    entry.async_on_unload(coordinator.stop_keepalive)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MujCezConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
