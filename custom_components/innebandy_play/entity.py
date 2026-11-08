"""Gemensam enhetsinfo, så alla entiteter hamnar under samma lag."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import CONF_COMPANY, CONF_TEAM_NAME, DOMAIN


def team_device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.data[CONF_COMPANY])},
        name=entry.data[CONF_TEAM_NAME],
        manufacturer="Innebandy Play",
        model="Lag",
        entry_type=DeviceEntryType.SERVICE,
    )
