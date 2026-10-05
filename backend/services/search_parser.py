"""Parse a free-text flight search into structured from/to/dates using an LLM."""

import json
import re
from datetime import date
from typing import Optional

from schemas.search import ParsedSearch

from .airport_service import AirportService
from .llm_client import LLMClient

SEARCH_PARSE_PROMPT = """Parse the flight search into JSON. Today is {today} (use it for relative dates).

Return JSON only (no markdown):
{{"origin": {{"code": "3-letter IATA airport code or null", "city": "full city name"}}, "destination": {{"code": "...", "city": "..."}}, "depart_date": "YYYY-MM-DD", "return_date": "YYYY-MM-DD or null"}}

Rules:
- code: the primary passenger airport (JFK not NYC, LHR not LON, HND not TYO, ORD not CHI). Unsure? null.
- city: full spelled-out city name (e.g. "New York", not abbreviations).
- depart_date: nearest future occurrence; null if not mentioned.
- return_date: null for one-way or when not mentioned; never before depart_date.

Query: {query}"""

_IATA_RE = re.compile(r"^[A-Z]{3}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SearchParser:
    def __init__(self, llm: LLMClient, airports: AirportService):
        self.llm = llm
        self.airports = airports

    async def parse(self, query: str) -> ParsedSearch:
        prompt = SEARCH_PARSE_PROMPT.format(
            today=date.today().isoformat(), query=query.strip()
        )
        text = await self.llm.generate_json(prompt)
        extracted = self._extract_json(text) if text else {}
        print(f"[SearchParser] LLM extracted: {extracted}")

        origin = self._resolve_airport(extracted.get("origin"))
        destination = self._resolve_airport(extracted.get("destination"))
        depart_date = self._normalize_date(extracted.get("depart_date"))
        return_date = self._normalize_date(extracted.get("return_date"))

        if depart_date and return_date and return_date < depart_date:
            return_date = None

        missing = []
        if not origin:
            missing.append("origin")
        if not destination:
            missing.append("destination")
        if not depart_date:
            missing.append("depart_date")

        return ParsedSearch(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            missing_fields=missing,
        )

    @staticmethod
    def _extract_json(text: Optional[str]) -> dict:
        if not text:
            return {}
        raw = text.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _resolve_airport(self, value: object) -> Optional[str]:
        """Resolve an LLM {code, city} pair to a local IATA code."""
        code = ""
        city = ""
        if isinstance(value, dict):
            code = str(value.get("code") or "").strip().upper()
            city = str(value.get("city") or "").strip()
        elif isinstance(value, str):
            if _IATA_RE.match(value.strip().upper()):
                code = value.strip().upper()
            else:
                city = value.strip()
        if not code and not city:
            return None

        code = self.airports.resolve_metro_code(code)

        # 1) Exact code against local airports.json
        if code:
            airport = self.airports.get_by_code(code)
            if airport and airport.code:
                return airport.code.upper()

        # 2) City → primary IATA for every city in airports.json (+ alias overrides)
        if city:
            resolved = self.airports.resolve_city_code(city)
            if resolved:
                return resolved

        # 3) Fuzzy city/name search fallback
        if city:
            results = self.airports.search_airports(query=city, limit=25)
            with_code = [a for a in results if a.code]
            city_lower = city.lower()
            starts = [
                a for a in with_code
                if a.name.lower().startswith(city_lower)
                or a.city.lower().startswith(city_lower)
            ]
            for airport in starts:
                if "international" in airport.name.lower():
                    return airport.code.upper()
            if starts:
                return starts[0].code.upper()
            for airport in with_code:
                if airport.city.lower() == city_lower:
                    return airport.code.upper()

        return None

    @staticmethod
    def _normalize_date(value: object) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        candidate = value.strip()
        if not _DATE_RE.match(candidate):
            return None
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            return None
