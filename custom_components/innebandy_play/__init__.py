"""Innebandy Play för Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InnebandyPlayApi
from .const import CONF_COMPANY, CONF_GROUP_ID, CONF_TEAM_NAME, DOMAIN
from .coordinator import InnebandyPlayCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
SERVICE_REFRESH = "refresh"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = InnebandyPlayApi(async_get_clientsession(hass))
    coordinator = InnebandyPlayCoordinator(
        hass,
        api,
        entry.data[CONF_COMPANY],
        entry.data[CONF_TEAM_NAME],
        entry.options.get(CONF_GROUP_ID),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        hass.services.async_register(DOMAIN, SERVICE_REFRESH, _async_handle_refresh)
    return True


async def _async_handle_refresh(call: ServiceCall) -> None:
    company = call.data.get("company")
    for entry in call.hass.config_entries.async_loaded_entries(DOMAIN):
        if company and entry.data[CONF_COMPANY] != company:
            continue
        await entry.runtime_data.async_force_refresh()


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
