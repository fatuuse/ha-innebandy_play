"""HTTP-klient mot solidsports endpoints."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import (
    API_BASE,
    EXTERNAL_SYSTEM,
    GAMES_PER_PAGE,
    REPLAYS_PER_PAGE,
    ROOT_CHANNEL,
    SQUAD_URL,
    STANDINGS_URL,
)


class InnebandyPlayError(Exception):
    """Kunde inte hämta data från API:et."""


def _rows(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


class InnebandyPlayApi:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            async with self._session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise InnebandyPlayError(str(err)) from err

    async def search_teams(self, query: str) -> list[dict[str, Any]]:
        data = await self._get(
            f"{API_BASE}/search/general",
            {
                "query": query,
                "page": 1,
                "per_page": 25,
                "autocomplete": "true",
                "root_channel": ROOT_CHANNEL,
                "external_system": EXTERNAL_SYSTEM,
            },
        )
        return [
            item
            for item in _rows(data)
            if item.get("content_type") == "channel"
            and item.get("filter") == "team"
            and item.get("slug")
        ]

    async def get_upcoming(self, company: str) -> list[dict[str, Any]]:
        return _rows(
            await self._get(
                f"{API_BASE}/timeline_objects/collections/games",
                {
                    "company": company,
                    "page": 1,
                    "per_page": GAMES_PER_PAGE,
                    "include_games_without_livestreams": "true",
                },
            )
        )

    async def get_replays(self, company: str) -> list[dict[str, Any]]:
        return _rows(
            await self._get(
                f"{API_BASE}/timeline_objects/collections/videos_and_replays",
                {"company": company, "page": 1, "per_page": REPLAYS_PER_PAGE},
            )
        )

    async def get_events(self, ident: str) -> list[dict[str, Any]] | None:
        data = await self._get(f"{API_BASE}/game/{ident}/events")
        if data is None:
            return None
        return _rows(data)

    async def get_metadata(self, ident: str) -> dict[str, Any]:
        data = await self._get(f"{API_BASE}/game/{ident}/metadata")
        return data if isinstance(data, dict) else {}

    async def get_standings(self, group_id: int) -> dict[str, Any] | None:
        data = await self._get(
            STANDINGS_URL,
            {"externalSystemId": EXTERNAL_SYSTEM, "eventReference": group_id},
        )
        return data if isinstance(data, dict) else None

    async def get_squad(self, team_id: int) -> list[dict[str, Any]] | None:
        data = await self._get(
            SQUAD_URL, {"externalSystem": EXTERNAL_SYSTEM, "ids": team_id}
        )
        if data is None:
            return None
        return _rows(data)
