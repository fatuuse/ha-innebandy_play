"""Knapp under lagets enhet som hämtar matchdata på nytt direkt."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_COMPANY
from .coordinator import InnebandyPlayCoordinator
from .entity import team_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([InnebandyRefreshButton(entry.runtime_data, entry)])


class InnebandyRefreshButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: InnebandyPlayCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.data[CONF_COMPANY]}_refresh"
        self._attr_device_info = team_device_info(entry)

    async def async_press(self) -> None:
        await self._coordinator.async_force_refresh()
