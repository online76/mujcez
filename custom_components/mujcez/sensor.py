"""Senzory odběrných míst Můj ČEZ."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
import re
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MujCezCoordinator

CZK = "CZK"


def _d(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


def _g(obj: dict | None, key: str) -> Any:
    return (obj or {}).get(key)


@dataclass(frozen=True, kw_only=True)
class MujCezSensorDescription(SensorEntityDescription):
    value: Callable[[dict[str, Any]], Any]
    attrs: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    available_if: Callable[[dict[str, Any]], bool] | None = None
    unit_fn: Callable[[dict[str, Any]], str] | None = None


SENSORS: tuple[MujCezSensorDescription, ...] = (
    MujCezSensorDescription(
        key="k_uhrade",
        name="K úhradě",
        icon="mdi:cash-clock",
        native_unit_of_measurement=CZK,
        device_class=SensorDeviceClass.MONETARY,
        value=lambda p: p["k_uhrade"],
        attrs=lambda p: {"splatnost": p["k_uhrade_splatnost"], "doklady": p["nezaplacene"]},
    ),
    MujCezSensorDescription(
        key="zaloha",
        name="Záloha",
        icon="mdi:cash-sync",
        native_unit_of_measurement=CZK,
        device_class=SensorDeviceClass.MONETARY,
        value=lambda p: p["zaloha"],
        attrs=lambda p: {
            "frekvence": p["zaloha_frekvence"],
            "pristi_splatnost": p["zaloha_pristi"],
            "posledni_v_obdobi": p["zaloha_posledni"],
            "zbyva_plateb": p["zaloha_zbyva_plateb"],
            "lze_zmenit": p["zaloha_lze_zmenit"],
            "proc_nelze_zmenit": p["zaloha_proc_nelze"],
            "zpusob_platby": p["platba_zaloh"],
        },
    ),
    MujCezSensorDescription(
        key="pristi_zaloha",
        name="Příští záloha",
        icon="mdi:calendar-cash",
        device_class=SensorDeviceClass.DATE,
        value=lambda p: _d(p["zaloha_pristi"]),
    ),
    MujCezSensorDescription(
        key="stav_meridla",
        name="Stav měřidla",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_fn=lambda p: p["jednotka_meridla"],
        value=lambda p: _g(p["posledni_odecet"], "vt"),
        attrs=lambda p: {
            "datum": _g(p["posledni_odecet"], "datum"),
            "zpusob": _g(p["posledni_odecet"], "zpusob"),
            "meridlo": p["meridlo"],
            "spotreba_od_minula": _g(p["posledni_odecet"], "spotreba"),
            "historie": p["odecty"],
        },
    ),
    MujCezSensorDescription(
        key="stav_meridla_nt",
        name="Stav měřidla NT",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda p: _g(p["posledni_odecet"], "nt"),
        available_if=lambda p: p["komodita"] == "elektrina" and p["dvoutarif"],
        attrs=lambda p: {"datum": _g(p["posledni_odecet"], "datum")},
    ),
    MujCezSensorDescription(
        key="posledni_odecet",
        name="Poslední odečet",
        icon="mdi:calendar-check",
        device_class=SensorDeviceClass.DATE,
        value=lambda p: _d(_g(p["posledni_odecet"], "datum")),
    ),
    MujCezSensorDescription(
        key="spotreba_obdobi",
        name="Spotřeba za poslední období",
        icon="mdi:chart-bar",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda p: _g(p["posledni_obdobi"], "kwh"),
        attrs=lambda p: {
            "od": _g(p["posledni_obdobi"], "od"),
            "do": _g(p["posledni_obdobi"], "do"),
            "vt": _g(p["posledni_obdobi"], "vt"),
            "nt": _g(p["posledni_obdobi"], "nt"),
            "naklad": _g(p["posledni_obdobi"], "kc"),
            "historie": p["spotreba_mesice"] or p["spotreba_roky"],
        },
    ),
    MujCezSensorDescription(
        key="naklad_obdobi",
        name="Náklad za poslední období",
        icon="mdi:cash",
        native_unit_of_measurement=CZK,
        device_class=SensorDeviceClass.MONETARY,
        value=lambda p: _g(p["posledni_obdobi"], "kc"),
        attrs=lambda p: {"od": _g(p["posledni_obdobi"], "od"), "do": _g(p["posledni_obdobi"], "do")},
    ),
    MujCezSensorDescription(
        key="spotreba_rok",
        name="Roční spotřeba",
        icon="mdi:chart-timeline-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda p: _g(p["posledni_rok"], "kwh"),
        attrs=lambda p: {
            "od": _g(p["posledni_rok"], "od"),
            "do": _g(p["posledni_rok"], "do"),
            "naklad": _g(p["posledni_rok"], "kc"),
            "historie": p["spotreba_roky"],
        },
    ),
    MujCezSensorDescription(
        key="posledni_vyuctovani",
        name="Poslední vyúčtování",
        icon="mdi:file-document-outline",
        native_unit_of_measurement=CZK,
        device_class=SensorDeviceClass.MONETARY,
        value=lambda p: _g(p["posledni_vyuctovani"], "castka"),
        attrs=lambda p: dict(p["posledni_vyuctovani"] or {}),
    ),
    MujCezSensorDescription(
        key="produkt",
        name="Produkt",
        icon="mdi:file-sign",
        value=lambda p: p["produkt"] or None,
        attrs=lambda p: {
            "typ": p["produkt_typ"],
            "platnost_od": p["produkt_od"],
            "platnost_do": p["produkt_do"],
            "smlouva": p["smlouva_text"],
            "distributor": p["distributor"],
            "distribucni_sazba": p["sazba"],
            "jistic_a": p["jistic_a"],
            "faze": p["faze"],
        },
    ),
    MujCezSensorDescription(
        key="prehled",
        name="Přehled",
        icon="mdi:card-account-details-outline",
        value=lambda p: p["nazev"],
        attrs=lambda p: {"mujcez_prehled": True, **p},
    ),
)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: MujCezCoordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add() -> None:
        new = []
        for code, point in (coordinator.data or {}).items():
            for desc in SENSORS:
                uid = f"{code}_{desc.key}"
                if uid in known or (desc.available_if and not desc.available_if(point)):
                    continue
                known.add(uid)
                new.append(MujCezSensor(coordinator, code, desc))
        if new:
            async_add_entities(new)

    _add()
    entry.async_on_unload(coordinator.async_add_listener(_add))


class MujCezSensor(CoordinatorEntity[MujCezCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: MujCezSensorDescription

    def __init__(self, coordinator: MujCezCoordinator, code: str, desc: MujCezSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = desc
        self._code = code
        p = coordinator.data[code]
        self._attr_unique_id = f"{DOMAIN}_{code}_{desc.key}"
        self.entity_id = f"sensor.mujcez_{p['komodita']}_{_slug(code)[-6:]}_{desc.key}"
        if desc.key == "prehled":
            self._unrecorded_attributes = frozenset(p.keys()) | {"mujcez_prehled"}
        elif desc.attrs:
            self._unrecorded_attributes = frozenset({"historie", "doklady"})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, code)},
            name=p["nazev"],
            manufacturer="ČEZ Prodej",
            model=("Elektřina" if p["komodita"] == "elektrina" else "Plyn") + (f" · {p['produkt']}" if p["produkt"] else ""),
            serial_number=code,
            configuration_url="https://muj.cez.cz/col/odberne-misto/" + (p.get("uid") or ""),
        )

    @property
    def _point(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(self._code)

    @property
    def available(self) -> bool:
        return super().available and self._point is not None

    @property
    def native_unit_of_measurement(self) -> str | None:
        p = self._point
        if self.entity_description.unit_fn and p:
            return self.entity_description.unit_fn(p)
        return self.entity_description.native_unit_of_measurement

    @property
    def device_class(self) -> SensorDeviceClass | None:
        p = self._point
        if self.entity_description.key == "stav_meridla" and p:
            return SensorDeviceClass.GAS if p["komodita"] == "plyn" else SensorDeviceClass.ENERGY
        return self.entity_description.device_class

    @property
    def native_value(self) -> Any:
        p = self._point
        return self.entity_description.value(p) if p else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        p = self._point
        if not p or not self.entity_description.attrs:
            return None
        return self.entity_description.attrs(p)
