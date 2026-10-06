"""Local airport lookup from data/airports.json (no network on the hot path)."""

from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from collections.abc import AsyncGenerator
from functools import lru_cache
from pathlib import Path

from schemas.airport import Airport

_AIRPORTS_PATH = Path(__file__).resolve().parent.parent / "data" / "airports.json"
_ALIASES_PATH = Path(__file__).resolve().parent.parent / "data" / "airport_aliases.json"

# Prefer passenger hubs when a city has several airports and no override.
_SECONDARY_NAME_HINTS = (
    "midway",
    "love field",
    "gatwick",
    "stansted",
    "luton",
    "orly",
    "laguardia",
    "city airport",
    "santa monica",
)


def _fold_key(value: str) -> str:
    """Uppercase ASCII key: 'São Paulo' → 'SAO PAULO', 'Cancún' → 'CANCUN'."""
    normalized = unicodedata.normalize("NFKD", (value or "").strip())
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_only.upper()


def _airport_priority(airport: Airport) -> tuple[int, int, str]:
    name = airport.name.lower()
    secondary = any(hint in name for hint in _SECONDARY_NAME_HINTS)
    international = "international" in name
    # Lower tuple sorts first: prefer non-secondary, then international, then code.
    return (1 if secondary else 0, 0 if international else 1, airport.code)


@lru_cache(maxsize=1)
def _load_aliases() -> tuple[dict[str, str], dict[str, str]]:
    """Load metro + preferred-city maps used only to normalize against local airports."""
    with _ALIASES_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    metro = {
        str(k).strip().upper(): str(v).strip().upper()
        for k, v in (data.get("metro_codes") or {}).items()
        if k and v
    }
    preferred = {
        _fold_key(str(k)): str(v).strip().upper()
        for k, v in (data.get("city_codes") or {}).items()
        if k and v
    }
    return metro, preferred


@lru_cache(maxsize=1)
def _load_airports() -> tuple[
    tuple[Airport, ...],
    dict[str, Airport],
    dict[str, str],
]:
    with _AIRPORTS_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)

    airports: list[Airport] = []
    by_code: dict[str, Airport] = {}
    by_city: dict[str, list[Airport]] = defaultdict(list)

    for row in raw:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "").strip().upper()
        if not code or code in by_code:
            continue
        airport = Airport(
            code=code,
            name=str(row.get("name") or "").strip(),
            city=str(row.get("city") or "").strip(),
            country=str(row.get("country") or "").strip(),
        )
        airports.append(airport)
        by_code[code] = airport
        city_key = _fold_key(airport.city)
        if city_key:
            by_city[city_key].append(airport)

    _, preferred = _load_aliases()
    city_to_code: dict[str, str] = {}

    for city_key, candidates in by_city.items():
        override = preferred.get(city_key)
        if override and override in by_code:
            city_to_code[city_key] = override
            continue
        best = sorted(candidates, key=_airport_priority)[0]
        city_to_code[city_key] = best.code

    for alias, code in preferred.items():
        if code in by_code:
            city_to_code.setdefault(alias, code)

    return tuple(airports), by_code, city_to_code


class AirportService:
    """In-memory airport search backed by a local JSON file."""

    def get_by_code(self, code: str) -> Airport | None:
        wanted = (code or "").strip().upper()
        if not wanted:
            return None
        _, by_code, _ = _load_airports()
        return by_code.get(wanted)

    def resolve_metro_code(self, code: str) -> str:
        """Map metro IATA (NYC, TYO) to a concrete airport code when known."""
        wanted = (code or "").strip().upper()
        if not wanted:
            return ""
        metro, _ = _load_aliases()
        return metro.get(wanted, wanted)

    def resolve_city_code(self, city: str) -> str | None:
        """Resolve an exact city name to a primary IATA in airports.json."""
        key = _fold_key(city)
        if not key:
            return None
        _, by_code, city_to_code = _load_airports()
        code = city_to_code.get(key)
        if code and code in by_code:
            return code
        return None

    def search_airports(self, query: str, limit: int = 10) -> list[Airport]:
        q = (query or "").strip().lower()
        if not q:
            return []
        folded = _fold_key(query).lower()
        airports, _, _ = _load_airports()
        results: list[Airport] = []
        for airport in airports:
            if (
                q in airport.code.lower()
                or q in airport.name.lower()
                or q in airport.city.lower()
                or folded in _fold_key(airport.city).lower()
                or q in airport.country.lower()
            ):
                results.append(airport)
                if len(results) >= limit:
                    break
        return results

    def get_all_airports(self, limit: int = 50) -> list[Airport]:
        airports, _, _ = _load_airports()
        return list(airports[:limit])


async def get_airport_service() -> AsyncGenerator[AirportService, None]:
    yield AirportService()
