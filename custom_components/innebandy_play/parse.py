"""Tolkar svar från solidsport. Inga nätanrop här, så funktionerna går lätt att testa."""
from __future__ import annotations

import re
from typing import Any

from .const import DEFAULT_MATCH_LENGTH, TIMELINE_LIMIT

GK_RE = re.compile(r"^Målvakt\s*-\s*(In|Ut):\s*(.+?)\s+-\s+(.+)$")
MINUTES_RE = re.compile(r"(\d+)\s*min", re.IGNORECASE)
ICONS = {
    "score": "🥅",
    "penalty": "🟨",
    "game_start": "▶️",
    "period_start": "▶️",
    "period_end": "⏸️",
    "game_end": "🏁",
}
PHASE_TYPES = {"game_start", "period_start", "period_end", "game_end"}


def to_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fmt_clock(game_time: Any) -> str | None:
    seconds = to_int(game_time)
    if seconds is None:
        return None
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def side_for_team(team_text: str, home: str, away: str) -> str | None:
    needle = _norm(team_text)
    if not needle:
        return None
    if needle in _norm(home):
        return "home"
    if needle in _norm(away):
        return "away"
    return None


def parse_game(raw: dict[str, Any], company: str) -> dict[str, Any] | None:
    ident = raw.get("ident")
    start = to_int(raw.get("start_at"))
    if not ident or start is None:
        return None
    end = to_int(raw.get("end_at")) or start + DEFAULT_MATCH_LENGTH

    home = raw.get("home_team") or {}
    away = raw.get("away_team") or {}
    home_name = (home.get("name") or "").strip()
    away_name = (away.get("name") or "").strip()

    our_side = None
    if home.get("channel_slug") == company:
        our_side = "home"
    elif away.get("channel_slug") == company:
        our_side = "away"

    opponent = None
    if our_side == "home":
        opponent = away_name
    elif our_side == "away":
        opponent = home_name

    location = raw.get("location") or {}
    event = raw.get("event") or {}
    price = raw.get("price") or {}
    return {
        "ident": ident,
        "title": raw.get("title") or f"{home_name} - {away_name}",
        "start_at": start,
        "end_at": end,
        "home_team": home_name,
        "away_team": away_name,
        "opponent": opponent,
        "our_side": our_side,
        "location": (location.get("name") or "").strip() or None,
        "league": (event.get("name") or "").strip() or None,
        "has_livestream": bool(raw.get("has_livestream")),
        "is_replay": bool(raw.get("is_replay")),
        "price_sek": to_int(price.get("SEK")) if isinstance(price, dict) else None,
    }


def summarize_events(events: list[dict[str, Any]], game: dict[str, Any]) -> dict[str, Any]:
    ours = game.get("our_side")
    home_name = game.get("home_team") or ""
    away_name = game.get("away_team") or ""
    ordered = sorted(
        events,
        key=lambda e: (to_int(e.get("activity_at")) or 0, to_int(e.get("created_at")) or 0),
    )

    types = [e.get("activity_type") for e in ordered]
    last_phase = next((t for t in reversed(types) if t in PHASE_TYPES), None)
    if "game_end" in types:
        status = "ended"
    elif last_phase == "period_end":
        status = "intermission"
    elif last_phase in ("game_start", "period_start"):
        status = "live"
    else:
        status = "not_started"

    home_score = away_score = period = None
    goals: list[dict[str, Any]] = []
    penalties: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []
    goalkeepers: dict[str, str | None] = {"home": None, "away": None}

    for e in ordered:
        kind = e.get("activity_type")
        text = (e.get("text") or "").strip()

        if kind == "comment":
            match = GK_RE.match(text)
            if match:
                action, team_part, name = match.group(1), match.group(2), match.group(3).strip()
                side = side_for_team(team_part, home_name, away_name)
                if side and action == "In":
                    goalkeepers[side] = name
                elif side and goalkeepers[side] == name:
                    goalkeepers[side] = None
            continue

        if e.get("home_score") is not None and e.get("away_score") is not None:
            home_score = to_int(e.get("home_score"))
            away_score = to_int(e.get("away_score"))

        ev_period = to_int(e.get("period"))
        if ev_period is not None:
            period = ev_period

        side = e.get("side") if e.get("side") in ("home", "away") else None
        is_ours = side is not None and side == ours
        clock = fmt_clock(e.get("game_time"))

        timeline.append({
            "time": clock,
            "period": ev_period,
            "icon": ICONS.get(kind, "•"),
            "text": text,
            "type": kind,
            "side": side,
            "ours": is_ours,
        })

        if kind == "score":
            goals.append({
                "time": clock,
                "period": ev_period,
                "side": side,
                "ours": is_ours,
                "team": e.get("team_name") or None,
                "scorer": e.get("player_name") or None,
                "number": e.get("player_number") or None,
                "assist": e.get("second_player_name") or None,
                "assist_number": e.get("second_player_number") or None,
                "home_score": to_int(e.get("home_score")),
                "away_score": to_int(e.get("away_score")),
                "text": text,
            })
        elif kind == "penalty":
            value = e.get("value") or ""
            minutes = MINUTES_RE.search(value)
            penalties.append({
                "time": clock,
                "period": ev_period,
                "side": side,
                "ours": is_ours,
                "player": e.get("player_name") or None,
                "number": e.get("player_number") or None,
                "reason": value.split(",")[0].strip() or None,
                "minutes": int(minutes.group(1)) if minutes else None,
                "text": text,
            })

    return {
        "status": status,
        "period": period,
        "home_score": home_score,
        "away_score": away_score,
        "goalkeeper_home": goalkeepers["home"],
        "goalkeeper_away": goalkeepers["away"],
        "goals": goals,
        "penalties": penalties,
        "timeline": timeline[::-1][:TIMELINE_LIMIT],
    }


def parse_standings(data: Any, company: str) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    table: list[dict[str, Any]] = []
    own: dict[str, Any] | None = None
    for row in data.get("rows") or []:
        if not isinstance(row, dict):
            continue
        pos = to_int(row.get("position"))
        name = (row.get("name") or "").strip()
        if pos is None or not name:
            continue
        item = {
            "pos": pos,
            "team": name,
            "team_id": to_int(row.get("id")),
            "slug": row.get("subdomain"),
            "own": row.get("subdomain") == company,
            "played": to_int(row.get("played")),
            "wins": to_int(row.get("wins")),
            "draws": to_int(row.get("draws")),
            "losses": to_int(row.get("losses")),
            "goals": row.get("goalsVsGoalsAgainst"),
            "goal_diff": to_int(row.get("goalsDifference")),
            "points": to_int(row.get("points")),
        }
        table.append(item)
        if item["own"]:
            own = item
    table.sort(key=lambda r: r["pos"])
    details = data.get("details") or {}
    return {
        "group": data.get("groupName") or details.get("name"),
        "table": table,
        "own": own,
    }


def parse_squad(data: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    players: list[dict[str, Any]] = []
    staff: list[dict[str, Any]] = []
    for section in (data if isinstance(data, list) else []):
        if not isinstance(section, dict):
            continue
        key = (section.get("details") or {}).get("key")
        for row in section.get("rows") or []:
            if not isinstance(row, dict):
                continue
            name = (row.get("name") or "").strip()
            if not name:
                continue
            if key == "team_rooster":
                players.append({
                    "number": to_int(row.get("number")),
                    "name": name,
                    "id": row.get("id"),
                    "position": row.get("position") or None,
                })
            elif key == "team_staff":
                staff.append({"name": name, "role": row.get("role") or None})
    players.sort(key=lambda p: (p["number"] is None, p["number"] or 0, p["name"]))
    return players, staff
