"""Koordinator som sammanställer all data för ett lag."""
from __future__ import annotations

import logging
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import InnebandyPlayApi, InnebandyPlayError
from .const import (
    CACHE_LIMIT,
    DOMAIN,
    INTERVAL_IDLE,
    INTERVAL_LIVE,
    MAX_BACKFILL_PER_CYCLE,
    METADATA_REFRESH,
    POST_GAME_WINDOW,
    PRE_GAME_WINDOW,
    RESULTS_LIMIT,
    SCHEDULE_HOUR,
    SCHEDULE_WEEKDAYS,
    SCORERS_LIMIT,
    SQUAD_REFRESH,
    STANDINGS_REFRESH,
    UPCOMING_LIMIT,
)
from .parse import parse_game, parse_squad, parse_standings, summarize_events

_LOGGER = logging.getLogger(__name__)
PRUNE_AFTER = 14 * 24 * 3600


def local_iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return dt_util.as_local(datetime.fromtimestamp(ts, tz=timezone.utc)).isoformat()


def _local_now(ts: float) -> datetime:
    return dt_util.as_local(datetime.fromtimestamp(ts, tz=timezone.utc))


def _local_date(ts: float) -> str:
    return _local_now(ts).strftime("%Y-%m-%d")


def _schedule_due(now: float, last_fetch: float) -> bool:
    """Sant om schemalagd hämtning (lör/sön kl. 08) har passerat sedan senaste hämtning."""
    local = _local_now(now)
    if local.weekday() not in SCHEDULE_WEEKDAYS or local.hour < SCHEDULE_HOUR:
        return False
    slot = local.replace(hour=SCHEDULE_HOUR, minute=0, second=0, microsecond=0)
    return last_fetch < slot.timestamp()


def _next_schedule_slot(now: float) -> float:
    local = _local_now(now)
    for offset in range(8):
        slot = (local + timedelta(days=offset)).replace(
            hour=SCHEDULE_HOUR, minute=0, second=0, microsecond=0
        )
        if slot.weekday() in SCHEDULE_WEEKDAYS and slot.timestamp() > now:
            return slot.timestamp()
    return now + INTERVAL_IDLE


def _empty_summary() -> dict[str, Any]:
    return {
        "status": "unknown",
        "period": None,
        "home_score": None,
        "away_score": None,
        "goalkeeper_home": None,
        "goalkeeper_away": None,
        "goals": [],
        "penalties": [],
        "timeline": [],
    }


def _game_public(game: dict[str, Any]) -> dict[str, Any]:
    return {
        "ident": game["ident"],
        "title": game["title"],
        "start": local_iso(game["start_at"]),
        "start_unix": game["start_at"],
        "location": game["location"],
        "home_team": game["home_team"],
        "away_team": game["away_team"],
        "opponent": game["opponent"],
        "is_home": game["our_side"] == "home",
        "has_livestream": game["has_livestream"],
        "league": game["league"],
    }


def _build_current(game: dict[str, Any] | None, summary: dict[str, Any] | None) -> dict[str, Any]:
    if game is None:
        return {
            "status": "none", "ident": None, "title": None, "home_team": None,
            "away_team": None, "home_score": None, "away_score": None, "score": None,
            "period": None, "location": None, "start": None, "is_home": None,
            "goalkeeper_home": None, "goalkeeper_away": None, "goalkeeper_ours": None,
            "goals": [], "penalties": [], "timeline": [],
        }

    s = summary or _empty_summary()
    ours = game["our_side"]
    status = s["status"]
    home, away = s["home_score"], s["away_score"]
    if status in ("live", "intermission", "ended"):
        home = 0 if home is None else home
        away = 0 if away is None else away
    else:
        home = away = None

    return {
        "status": status,
        "ident": game["ident"],
        "title": game["title"],
        "home_team": game["home_team"],
        "away_team": game["away_team"],
        "home_score": home,
        "away_score": away,
        "score": f"{home}-{away}" if home is not None and away is not None else None,
        "period": s["period"],
        "location": game["location"],
        "start": local_iso(game["start_at"]),
        "is_home": ours == "home",
        "goalkeeper_home": s["goalkeeper_home"],
        "goalkeeper_away": s["goalkeeper_away"],
        "goalkeeper_ours": s[f"goalkeeper_{ours}"] if ours else None,
        "goals": s["goals"],
        "penalties": s["penalties"],
        "timeline": s["timeline"],
    }


class InnebandyPlayCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        api: InnebandyPlayApi,
        company: str,
        team_name: str,
        group_id: int | None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {team_name}",
            update_interval=timedelta(seconds=INTERVAL_IDLE),
        )
        self.api = api
        self.company = company
        self.team_name = team_name
        self.group_id = group_id

        self._games: dict[str, dict[str, Any]] = {}
        self._schedule_at = 0.0
        self._cache: dict[str, dict[str, Any]] = {}
        self._league: dict[str, Any] = {}
        self._league_at = 0.0
        self._standings: dict[str, Any] | None = None
        self._standings_at = 0.0
        self._squad: dict[str, Any] | None = None
        self._squad_at = 0.0

    async def async_force_refresh(self) -> None:
        self._schedule_at = 0.0
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        now = time.time()
        errors = await self._refresh_sources(now)
        if not self._games and errors:
            raise UpdateFailed("; ".join(errors))

        upcoming = sorted(
            (g for g in self._games.values() if g["start_at"] > now),
            key=lambda g: g["start_at"],
        )
        candidate = self._current_candidate(now)
        summary = await self._load_summary(candidate) if candidate else None
        current = _build_current(candidate, summary)

        past = sorted(
            (
                g
                for g in self._games.values()
                if g["start_at"] <= now
                and (candidate is None or g["ident"] != candidate["ident"])
            ),
            key=lambda g: g["start_at"],
            reverse=True,
        )
        await self._backfill(past, now)

        results = self._result_rows(past)
        form = "".join(r["result"] for r in results if r["result"])[:5]
        record = {
            key: sum(1 for r in results if r["result"] == code)
            for key, code in (("wins", "V"), ("draws", "O"), ("losses", "F"))
        }
        scorers, scorer_games = self._scorers()

        reference = candidate or (upcoming[0] if upcoming else None) or (past[0] if past else None)
        await self._refresh_optional(now, reference)

        self.update_interval = timedelta(seconds=self._interval(now, current, upcoming))

        return {
            "company": self.company,
            "team": self.team_name,
            "current": current,
            "last_event": current["timeline"][0] if current["timeline"] else None,
            "next_game": _game_public(upcoming[0]) if upcoming else None,
            "upcoming": [_game_public(g) for g in upcoming[:UPCOMING_LIMIT]],
            "results": results,
            "form": form,
            "record": record,
            "scorers": scorers,
            "scorers_games": scorer_games,
            "standings": self._standings,
            "squad": self._squad_public(current),
            "league": self._league,
        }

    def _merge(self, raw_games: list[dict[str, Any]]) -> None:
        for raw in raw_games:
            game = parse_game(raw, self.company)
            if game:
                self._games[game["ident"]] = game

    async def _refresh_sources(self, now: float) -> list[str]:
        errors: list[str] = []
        if self._schedule_at == 0.0 or _schedule_due(now, self._schedule_at):
            try:
                self._merge(await self.api.get_upcoming(self.company))
                self._merge(await self.api.get_replays(self.company))
                self._schedule_at = now
            except InnebandyPlayError as err:
                errors.append(f"matchlista: {err}")
        for ident, game in list(self._games.items()):
            if game["end_at"] < now - PRUNE_AFTER and ident not in self._cache:
                del self._games[ident]
        return errors

    def _current_candidate(self, now: float) -> dict[str, Any] | None:
        windows = [
            g
            for g in self._games.values()
            if g["start_at"] - PRE_GAME_WINDOW <= now <= g["end_at"] + POST_GAME_WINDOW
        ]
        return min(windows, key=lambda g: g["start_at"]) if windows else None

    def _store(self, game: dict[str, Any], summary: dict[str, Any]) -> None:
        self._cache[game["ident"]] = {"game": game, "summary": summary}
        while len(self._cache) > CACHE_LIMIT:
            del self._cache[next(iter(self._cache))]

    async def _load_summary(self, game: dict[str, Any]) -> dict[str, Any] | None:
        entry = self._cache.get(game["ident"])
        if entry:
            return entry["summary"]
        try:
            events = await self.api.get_events(game["ident"])
        except InnebandyPlayError as err:
            _LOGGER.warning("Kunde inte hämta händelser för %s: %s", game["title"], err)
            return None
        if events is None:
            return None
        summary = summarize_events(events, game)
        if summary["status"] == "ended":
            self._store(game, summary)
        return summary

    async def _backfill(self, past: list[dict[str, Any]], now: float) -> None:
        fetched = 0
        for game in past:
            if fetched >= MAX_BACKFILL_PER_CYCLE:
                break
            if game["ident"] in self._cache:
                continue
            if now < game["end_at"] + POST_GAME_WINDOW or now - game["end_at"] > PRUNE_AFTER:
                continue
            fetched += 1
            try:
                events = await self.api.get_events(game["ident"])
            except InnebandyPlayError as err:
                _LOGGER.debug("Kunde inte fylla på resultat för %s: %s", game["title"], err)
                continue
            if events is None:
                self._store(game, _empty_summary())
            else:
                self._store(game, summarize_events(events, game))

    def _result_rows(self, past: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for game in past[:RESULTS_LIMIT]:
            entry = self._cache.get(game["ident"])
            summary = entry["summary"] if entry else None
            home = summary["home_score"] if summary else None
            away = summary["away_score"] if summary else None
            side = game["our_side"]

            result = None
            if (
                summary
                and summary["status"] == "ended"
                and home is not None
                and away is not None
                and side
            ):
                ours_goals, theirs = (home, away) if side == "home" else (away, home)
                result = "V" if ours_goals > theirs else ("F" if ours_goals < theirs else "O")

            scorers = (
                [g["scorer"] for g in summary["goals"] if g["ours"] and g["scorer"]]
                if summary
                else []
            )
            rows.append({
                "date": _local_date(game["start_at"]),
                "start": local_iso(game["start_at"]),
                "ident": game["ident"],
                "opponent": game["opponent"],
                "is_home": side == "home",
                "score": f"{home}-{away}" if home is not None and away is not None else None,
                "result": result,
                "scorers": scorers,
                "location": game["location"],
                "replay": game["is_replay"],
            })
        return rows

    def _scorers(self) -> tuple[list[dict[str, Any]], int]:
        goals: Counter[str] = Counter()
        assists: Counter[str] = Counter()
        numbers: dict[str, str | None] = {}
        games = 0
        for entry in self._cache.values():
            game, summary = entry["game"], entry["summary"]
            if not game["our_side"] or summary["status"] != "ended":
                continue
            games += 1
            for goal in summary["goals"]:
                if not goal["ours"]:
                    continue
                if goal["scorer"]:
                    goals[goal["scorer"]] += 1
                    numbers.setdefault(goal["scorer"], goal["number"])
                if goal["assist"]:
                    assists[goal["assist"]] += 1
                    numbers.setdefault(goal["assist"], goal["assist_number"])

        rows = [
            {
                "name": name,
                "number": numbers.get(name),
                "goals": goals[name],
                "assists": assists[name],
                "points": goals[name] + assists[name],
            }
            for name in set(goals) | set(assists)
        ]
        rows.sort(key=lambda r: (-r["points"], -r["goals"], r["name"]))
        return rows[:SCORERS_LIMIT], games

    async def _refresh_optional(self, now: float, reference: dict[str, Any] | None) -> None:
        if reference:
            try:
                await self._refresh_league(now, reference["ident"])
            except InnebandyPlayError as err:
                _LOGGER.debug("Kunde inte hämta serie: %s", err)
        try:
            await self._refresh_standings(now)
        except InnebandyPlayError as err:
            _LOGGER.warning("Kunde inte hämta tabellen: %s", err)
        try:
            await self._refresh_squad(now)
        except InnebandyPlayError as err:
            _LOGGER.warning("Kunde inte hämta truppen: %s", err)

    async def _refresh_league(self, now: float, ident: str) -> None:
        if self._league_at and now - self._league_at < METADATA_REFRESH:
            return
        meta = await self.api.get_metadata(ident)
        league = meta.get("league") or {}
        district = meta.get("district") or {}
        location = meta.get("location") or {}
        self._league = {
            "id": league.get("id"),
            "name": (league.get("name") or "").strip() or None,
            "district": district.get("name"),
            "location": (location.get("name") or "").strip() or None,
        }
        self._league_at = now

    async def _refresh_standings(self, now: float) -> None:
        group = self.group_id or self._league.get("id")
        if not group:
            return
        if (
            self._standings
            and self._standings.get("group_id") == group
            and now - self._standings_at < STANDINGS_REFRESH
        ):
            return
        data = await self.api.get_standings(group)
        parsed = parse_standings(data, self.company) or {"group": None, "table": [], "own": None}
        parsed.update({
            "group_id": group,
            "source": "option" if self.group_id else "metadata",
            "updated": local_iso(now),
        })
        self._standings = parsed
        self._standings_at = now

    async def _refresh_squad(self, now: float) -> None:
        own = (self._standings or {}).get("own")
        if not own or not own.get("team_id"):
            return
        team_id = own["team_id"]
        if (
            self._squad
            and self._squad["team_id"] == team_id
            and now - self._squad_at < SQUAD_REFRESH
        ):
            return
        data = await self.api.get_squad(team_id)
        if data is None:
            return
        players, staff = parse_squad(data)
        self._squad = {
            "team_id": team_id,
            "players": players,
            "staff": staff,
            "updated": local_iso(now),
        }
        self._squad_at = now

    def _squad_public(self, current: dict[str, Any]) -> dict[str, Any] | None:
        if not self._squad:
            return None
        gk_now = current.get("goalkeeper_ours")
        players = []
        for p in self._squad["players"]:
            position = (p.get("position") or "").casefold()
            is_gk = "mål" in position or (bool(gk_now) and p["name"] == gk_now)
            players.append({**p, "goalkeeper": is_gk})
        return {
            "team_id": self._squad["team_id"],
            "players": players,
            "staff": self._squad["staff"],
            "updated": self._squad["updated"],
        }

    def _interval(self, now: float, current: dict[str, Any], upcoming: list[dict[str, Any]]) -> int:
        # Under matchfönstret: var 30:e sekund tills matchen är slut
        if current["ident"] and current["status"] != "ended":
            return INTERVAL_LIVE
        # Annars: vakna när nästa matchfönster eller nästa lör/sön kl. 08 börjar
        targets = [g["start_at"] - PRE_GAME_WINDOW for g in upcoming[:3]]
        targets.append(_next_schedule_slot(now))
        wait = min((t - now for t in targets if t > now), default=INTERVAL_IDLE)
        return int(max(30, min(wait, INTERVAL_IDLE)))
