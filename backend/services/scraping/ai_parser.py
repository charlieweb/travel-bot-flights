import json
import os
import asyncio
import re
from typing import Optional
from functools import partial

from schemas.travel import TravelOption

_AI_CONTENT_SLICE = 8_000

FLIGHT_EXTRACTION_PROMPT = """Extract flight fares from the snippets below. Return a JSON array only (no markdown).

Each object: airline, price (USD number), depart_time, arrival_time (12h "H:MM AM"), duration, stops (int), confidence (0-1).

Rules:
- One itinerary per object; price and times must come from the same row/card.
- "--- Row N ---" = at most one fare per block unless multiple distinct prices appear.
- Skip nav/ads; require airline + price + times.
- If none found, return [].

Site: {site_name} | {origin}->{destination} | {depart_date}{return_context}

{page_content}"""


def _normalize_usd_price(value: object) -> float | None:
    """Return a plausible economy fare in USD (one-way or round-trip), or None if invalid."""
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None
    if 50 <= price <= 15_000:
        return round(price, 2)
    # Rare AI mistake: cents stuffed into an integer (15552 -> 155.52), not real $15k+ fares
    if price > 15_000:
        scaled = price / 100
        if 50 <= scaled <= 15_000:
            return round(scaled, 2)
    return None


def _normalize_time_12h(value: object) -> str:
    """Best-effort normalize to 'H:MM AM/PM' for display and consistency."""
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return s
    s = re.sub(r"\s+", " ", s)
    # "6:45 AM", "6:45AM", "06:45 PM"
    m = re.match(
        r"^(\d{1,2}):(\d{2})\s*([AP])\.?\s*M\.?$",
        s,
        re.IGNORECASE,
    )
    if m:
        h, mn, ap = int(m.group(1)), m.group(2), m.group(3).upper()
        if 1 <= h <= 12 and len(mn) == 2:
            return f"{h}:{mn} {ap}M"
    # e.g. "645 AM" or "6 45 PM"
    m2 = re.match(r"^(\d{1,2})\s*:?\s*(\d{2})\s*([AP])\.?\s*M\.?$", s, re.IGNORECASE)
    if m2:
        h, mn, ap = int(m2.group(1)), m2.group(2), m2.group(3).upper()
        if 1 <= h <= 12:
            return f"{h}:{mn} {ap}M"
    return s


class AIParser:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        self._client = None
        self._available = None

    def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        if not self.api_key:
            print("[AIParser] No GOOGLE_API_KEY set, AI parsing disabled")
            self._available = False
            return False
        try:
            import google.genai
            self._available = True
            return True
        except ImportError:
            print("[AIParser] google-genai not installed, AI parsing disabled")
            self._available = False
            return False

    def _get_client(self):
        if self._client is None:
            from google.genai import Client
            self._client = Client(api_key=self.api_key)
        return self._client

    async def parse_flights(
        self,
        page_content: str,
        site_name: str,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None = None,
    ) -> list[dict]:
        if not self._check_available():
            return []

        return_context = f" | return {return_date}" if return_date else ""

        trimmed = page_content[:_AI_CONTENT_SLICE]
        prompt = FLIGHT_EXTRACTION_PROMPT.format(
            site_name=site_name,
            origin=origin.upper(),
            destination=destination.upper(),
            depart_date=depart_date,
            return_context=return_context,
            page_content=trimmed,
        )

        try:
            client = self._get_client()
            print(f"[AIParser] Calling {self.model} for {site_name} ({len(page_content)} chars)")

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                partial(
                    client.models.generate_content,
                    model=self.model,
                    contents=prompt,
                    config={
                        "temperature": 0.1,
                        "max_output_tokens": 4096,
                    },
                ),
            )

            text = response.text
            if not text:
                print(f"[AIParser] Empty model response for {site_name}")
                return []

            raw = text.strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

            flights = json.loads(raw)
            if not isinstance(flights, list):
                print(f"[AIParser] Response was not a list, got: {type(flights)}")
                return []

            flights = [
                f for f in flights
                if isinstance(f, dict)
                and f.get("airline")
                and f.get("price") is not None
                and f.get("confidence", 1) >= 0.3
            ]

            for f in flights:
                if isinstance(f, dict):
                    if f.get("depart_time") is not None:
                        f["depart_time"] = _normalize_time_12h(f["depart_time"])
                    if f.get("arrival_time") is not None:
                        f["arrival_time"] = _normalize_time_12h(f["arrival_time"])

            print(f"[AIParser] Extracted {len(flights)} flights from {site_name}")
            for f in flights:
                print(f"  {f.get('airline')} ${f.get('price')} {f.get('depart_time')}->{f.get('arrival_time')} stops={f.get('stops')}")

            return flights

        except json.JSONDecodeError as e:
            print(f"[AIParser] JSON parse error for {site_name}: {e}")
            print(f"[AIParser] Raw response (first 500): {raw[:500]}")
            return []
        except Exception as e:
            print(f"[AIParser] Error parsing {site_name}: {e}")
            return []

    def flights_to_options(
        self,
        flights: list[dict],
        start_id: int,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
        source_type: str,
        source_url: str = "",
    ) -> list[TravelOption]:
        options = []
        for f in flights:
            price = _normalize_usd_price(f.get("price"))
            if price is None:
                continue

            depart = f.get("depart_time", "08:00 AM")
            arrival = f.get("arrival_time", "11:00 AM")

            duration = f.get("duration", "2h 30m")
            stops = int(f.get("stops", 0))

            airline = (f.get("airline") or "").strip()
            lower = airline.lower().rstrip(".")
            if not airline or lower in (
                "flight option",
                "unknown",
                "google flights",
                "kayak",
                "skyscanner",
                "expedia",
                "to update prices",
                "update prices",
            ):
                continue
            if re.match(r"^to\s+[a-z]", airline, re.IGNORECASE):
                continue
            if "update" in lower and "price" in lower:
                continue

            options.append(TravelOption(
                id=start_id + len(options),
                airline=airline,
                price=price,
                depart_time=depart,
                arrival_time=arrival,
                duration=duration,
                stops=stops,
                source_url=source_url,
                source_type=source_type,
                depart_date=str(depart_date) if depart_date else None,
                return_date=str(return_date) if return_date else None,
            ))
        return options
