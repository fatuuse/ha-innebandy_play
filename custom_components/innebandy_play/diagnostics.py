"""Diagnostik som går att ladda ner från integrationens sida. Namn och spelare maskeras."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

TO_REDACT = {
    "name", "player", "players", "scorer", "assist", "staff", "text",
    "goalkeeper_home", "goalkeeper_away", "goalkeeper_ours",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "entry": entry.data,
        "options": entry.options,
        "update_interval_s": coordinator.update_interval.total_seconds(),
        "last_update_success": coordinator.last_update_success,
        "data": async_redact_data(coordinator.data, TO_REDACT),
    }
