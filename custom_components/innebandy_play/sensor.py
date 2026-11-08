"""Sensorer för nästa match, pågående match, händelser, tabell, resultat, målskyttar och trupp."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_COMPANY
from .coordinator import InnebandyPlayCoordinator
from .entity import team_device_info


def _value_next(d: dict[str, Any]) -> str | None:
    game = d["next_game"]
    return game["title"] if game else None


def _attrs_next(d: dict[str, Any]) -> dict[str, Any]:
    return {**(d["next_game"] or {}), "upcoming": d["upcoming"]}


def _value_current(d: dict[str, Any]) -> str | None:
    current = d["current"]
    if current["status"] in ("none", "unknown"):
        return None
    if current["status"] == "not_started":
        return "Ej startad"
    return current["score"]


def _attrs_current(d: dict[str, Any]) -> dict[str, Any]:
    return dict(d["current"])


def _value_last(d: dict[str, Any]) -> str | None:
    last = d["last_event"]
    return (last["text"] or "")[:250] if last else None


def _attrs_last(d: dict[str, Any]) -> dict[str, Any]:
    last = d["last_event"] or {}
    return {**last, "match": d["current"]["title"]}


def _value_standings(d: dict[str, Any]) -> int | None:
    own = ((d["standings"] or {}).get("own")) or None
    return own["pos"] if own else None


def _attrs_standings(d: dict[str, Any]) -> dict[str, Any]:
    s = d["standings"] or {}
    own = s.get("own") or {}
    table = s.get("table") or []
    return {
        "group": s.get("group"),
        "group_id": s.get("group_id"),
        "source": s.get("source"),
        "updated": s.get("updated"),
        "points": own.get("points"),
        "played": own.get("played"),
        "wins": own.get("wins"),
        "draws": own.get("draws"),
        "losses": own.get("losses"),
        "goals": own.get("goals"),
        "goal_diff": own.get("goal_diff"),
        "teams": len(table),
        "table": table,
    }


def _value_results(d: dict[str, Any]) -> str | None:
    results = d["results"]
    return results[0]["score"] if results else None


def _attrs_results(d: dict[str, Any]) -> dict[str, Any]:
    results = d["results"]
    return {
        "form": d["form"],
        "record": d["record"],
        "last_result": results[0]["result"] if results else None,
        "results": results,
    }


def _value_scorers(d: dict[str, Any]) -> str | None:
    rows = d["scorers"]
    return rows[0]["name"] if rows else None


def _attrs_scorers(d: dict[str, Any]) -> dict[str, Any]:
    return {"scorers": d["scorers"], "games": d["scorers_games"]}


def _value_squad(d: dict[str, Any]) -> int | None:
    squad = d["squad"]
    return len(squad["players"]) if squad else None


def _attrs_squad(d: dict[str, Any]) -> dict[str, Any]:
    squad = d["squad"] or {"players": [], "staff": [], "updated": None, "team_id": None}
    return {
        "players": squad["players"],
        "staff": squad["staff"],
        "updated": squad["updated"],
        "team_id": squad["team_id"],
    }


SENSORS: list[tuple[str, str, Callable, Callable, frozenset[str]]] = [
    ("next_game", "mdi:calendar-clock", _value_next, _attrs_next, frozenset({"upcoming"})),
    ("current_game", "mdi:hockey-sticks", _value_current, _attrs_current,
     frozenset({"timeline", "goals", "penalties"})),
    ("last_event", "mdi:whistle", _value_last, _attrs_last, frozenset()),
    ("standings", "mdi:format-list-numbered", _value_standings, _attrs_standings,
     frozenset({"table"})),
    ("results", "mdi:trophy-outline", _value_results, _attrs_results, frozenset({"results"})),
    ("scorers", "mdi:star-outline", _value_scorers, _attrs_scorers, frozenset({"scorers"})),
    ("squad", "mdi:account-group", _value_squad, _attrs_squad,
     frozenset({"players", "staff"})),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: InnebandyPlayCoordinator = entry.runtime_data
    async_add_entities([InnebandySensor(coordinator, entry, *spec) for spec in SENSORS])


class InnebandySensor(CoordinatorEntity[InnebandyPlayCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: InnebandyPlayCoordinator,
        entry: ConfigEntry,
        kind: str,
        icon: str,
        value_fn: Callable[[dict[str, Any]], Any],
        attrs_fn: Callable[[dict[str, Any]], dict[str, Any]],
        unrecorded: frozenset[str],
    ) -> None:
        super().__init__(coordinator)
        self._kind = kind
        self._value_fn = value_fn
        self._attrs_fn = attrs_fn
        self._attr_unique_id = f"{entry.data[CONF_COMPANY]}_{kind}"
        self._attr_translation_key = kind
        self._attr_icon = icon
        self._attr_device_info = team_device_info(entry)
        self._unrecorded_attributes = unrecorded

    @property
    def native_value(self) -> Any:
        return self._value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "kind": self._kind,
            "company": self.coordinator.company,
            "team": self.coordinator.team_name,
            **self._attrs_fn(self.coordinator.data),
        }
