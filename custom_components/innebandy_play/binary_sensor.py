"""Binär sensor som är på när matchen pågår."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_COMPANY
from .coordinator import InnebandyPlayCoordinator
from .entity import team_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([InnebandyLiveSensor(entry.runtime_data, entry)])


class InnebandyLiveSensor(CoordinatorEntity[InnebandyPlayCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "live"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: InnebandyPlayCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.data[CONF_COMPANY]}_live"
        self._attr_device_info = team_device_info(entry)

    @property
    def is_on(self) -> bool:
        return self.coordinator.data["current"]["status"] in ("live", "intermission")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator.data["current"]
        return {
            "status": c["status"],
            "title": c["title"],
            "score": c["score"],
            "start": c["start"],
            "team": self.coordinator.team_name,
            "company": self.coordinator.company,
        }
