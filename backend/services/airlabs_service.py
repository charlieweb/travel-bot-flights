import os
import time
import httpx
from middleware.error_handlers import (
    APIKeyNotConfiguredException,
    ExternalAPIException,
)
from schemas.airport import Airport


AIRLABS_API_URL = "https://airlabs.co/api/v9"


def get_airlabs_api_key() -> str:
    api_key = os.getenv("AIRLABS_API_KEY")
    if not api_key:
        raise APIKeyNotConfiguredException()
    return api_key


class AirLabsService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self._cache: list[dict] | None = None
        self._cache_at: float = 0.0

    async def close(self) -> None:
        await self.client.aclose()

    async def _fetch_airports(self) -> list[dict]:
        # Cache the full list for 6 hours; it changes rarely
        if self._cache is not None and (time.time() - self._cache_at) < 6 * 3600:
            return self._cache
        try:
            response = await self.client.get(
                f"{AIRLABS_API_URL}/airports",
                params={"api_key": self.api_key},
            )
            response.raise_for_status()
            data = response.json()
            airports = data.get("response") or []
            self._cache = airports
            self._cache_at = time.time()
            return airports
        except httpx.HTTPError as e:
            raise ExternalAPIException(detail=f"Error fetching airports: {str(e)}")

    async def get_by_code(self, code: str) -> Airport | None:
        """Exact IATA code lookup."""
        wanted = code.strip().upper()
        for airport in await self._fetch_airports():
            if (airport.get("iata_code") or "").upper() == wanted:
                return self._map_to_airport(airport)
        return None

    def _map_to_airport(self, raw: dict) -> Airport:
        return Airport(
            code=raw.get("iata_code") or "",
            name=raw.get("name") or "",
            city=raw.get("city") or "",
            country=raw.get("country_code") or "",
        )

    async def search_airports(self, query: str, limit: int = 10) -> list[Airport]:
        raw_airports = await self._fetch_airports()
        query_lower = query.lower()
        results = []

        for airport in raw_airports:
            code = airport.get("iata_code") or ""
            name = airport.get("name") or ""
            city = airport.get("city") or ""

            if (
                query_lower in code.lower()
                or query_lower in name.lower()
                or query_lower in city.lower()
            ):
                results.append(self._map_to_airport(airport))

            if len(results) >= limit:
                break

        return results

    async def get_all_airports(self, limit: int = 50) -> list[Airport]:
        raw_airports = await self._fetch_airports()
        return [self._map_to_airport(a) for a in raw_airports[:limit]]


from collections.abc import AsyncGenerator

async def get_airlabs_service() -> AsyncGenerator[AirLabsService, None]:
    service = AirLabsService(api_key=get_airlabs_api_key())
    try:
        yield service
    finally:
        await service.close()