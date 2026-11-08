"""Config flow: välj lag. Options flow: tabell-ID med validering."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import InnebandyPlayApi, InnebandyPlayError
from .const import CONF_COMPANY, CONF_GROUP_ID, CONF_QUERY, CONF_TEAM_NAME, DOMAIN
from .parse import parse_standings


class InnebandyPlayConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._teams: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            query = user_input[CONF_QUERY].strip()
            if len(query) < 2:
                errors["base"] = "query_too_short"
            else:
                api = InnebandyPlayApi(async_get_clientsession(self.hass))
                try:
                    found = await api.search_teams(query)
                except InnebandyPlayError:
                    errors["base"] = "cannot_connect"
                else:
                    self._teams = {
                        t["slug"]: (t.get("name") or t["slug"]).strip() for t in found
                    }
                    if self._teams:
                        return await self.async_step_team()
                    errors["base"] = "no_teams_found"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_QUERY): str}),
            errors=errors,
        )

    async def async_step_team(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            slug = user_input[CONF_COMPANY]
            name = self._teams.get(slug, slug)
            await self.async_set_unique_id(slug)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=name,
                data={CONF_COMPANY: slug, CONF_TEAM_NAME: name},
            )

        options = [SelectOptionDict(value=s, label=n) for s, n in self._teams.items()]
        return self.async_show_form(
            step_id="team",
            data_schema=vol.Schema({
                vol.Required(CONF_COMPANY): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                )
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return InnebandyPlayOptionsFlow()


class InnebandyPlayOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            group = user_input.get(CONF_GROUP_ID)
            if group:
                api = InnebandyPlayApi(async_get_clientsession(self.hass))
                try:
                    data = await api.get_standings(int(group))
                except InnebandyPlayError:
                    errors["base"] = "cannot_connect"
                else:
                    parsed = parse_standings(data, self.config_entry.data[CONF_COMPANY])
                    if not parsed or not parsed["own"]:
                        errors["base"] = "group_not_found"
            if not errors:
                return self.async_create_entry(
                    title="",
                    data={CONF_GROUP_ID: int(group) if group else None},
                )

        current = self.config_entry.options.get(CONF_GROUP_ID)
        schema = vol.Schema({
            vol.Optional(CONF_GROUP_ID, description={"suggested_value": current}): NumberSelector(
                NumberSelectorConfig(min=1, max=10_000_000, step=1, mode=NumberSelectorMode.BOX)
            )
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
