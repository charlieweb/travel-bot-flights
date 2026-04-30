"""
Main scraping service facade.

Provides a unified interface for flight search operations using
configured scraping providers (Firecrawl, Crawl4AI, etc.).
"""

import os
import re
from datetime import date
from typing import List, Optional

from schemas.travel import TravelOption
from .providers import get_provider, ScrapingProvider

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

AIRLINE_SITES = [
    ("Delta", "https://www.delta.com/flight-search/book-a-flight?departureDate={date_iso}&destinationAirportCode={destination}&originAirportCode={origin}&tripType=ONE_WAY&paxCount=1"),
    ("United", "https://www.united.com/en/us/fsr/ow/search?origin={origin}&destination={destination}&departDate={date_iso}&passengers=1"),
    ("American Airlines", "https://www.aa.com/booking/find-flights?origin={origin}&destination={destination}&departDate={date_iso}&passengers=1"),
    ("Southwest", "https://www.southwest.com/air/booking/select.html?originationAirportCode={origin}&destinationAirportCode={destination}&outboundDate={date_iso}&passengers=1"),
    ("Avianca", "https://www.avianca.com/en/flights/?origin={origin}&destination={destination}&departureDate={date_dash}&adults=1&currency=USD"),
    ("Copa Airlines", "https://www.copaair.com/en-us/flights?origin={origin}&destination={destination}&departDate={date_iso}&passengers=1"),
    ("Aeromexico", "https://www.aeromexico.com/en-us/flights?origin={origin}&destination={destination}&departDate={date_iso}&passengers=1"),
]

AGGREGATOR_SITES = [
    ("Google Flights", "https://www.google.com/travel/flights?q=flights+{origin}+to+{destination}+{month_name}+{day}+{year}"),
    ("Kayak", "https://www.kayak.com/flights/{origin}-{destination}/{date_dash}?sort=price_a"),
    ("Skyscanner", "https://www.skyscanner.com/transport/flights/{origin}/{destination}/{date_dash}/"),
    ("Expedia", "https://www.expedia.com/Flights-Search?flight-type=on&starDate={date_dash}&endDate=&trip=oneway&leg1=from%3A{origin}%2Cto%3A{destination}%2Cdeparture%3A{date_dash}TANYT&passengers=adults%3A1%2Cseniors%3A0%2Cchildren%3A0%2Cinfants%3A0&mode=search&options=cabinclass%3Aeconomy"),
]


class ScrapingService:
    """Main scraping service for flight search operations."""

    def __init__(self, provider: Optional[ScrapingProvider] = None):
        self.provider = provider or get_provider()

    async def search_travel_options(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: date,
    ) -> List[TravelOption]:
        """Search for travel options using the configured provider."""
        depart_date_str = str(depart_date) if depart_date else None
        return_date_str = str(return_date) if return_date else None

        try:
            results = await self._search_with_provider(
                origin, destination, depart_date_str, return_date_str
            )
            if results:
                return results
        except Exception as e:
            print(f"Provider search failed: {e}")

        return self._mock_results(origin, destination, depart_date_str, return_date_str)

    async def _search_with_provider(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str,
    ) -> List[TravelOption]:
        """Execute search using the configured provider."""
        results: List[TravelOption] = []
        result_id = 1

        # Try web search if provider supports it
        try:
            search_query = f"flights from {origin} to {destination} departing {depart_date}"
            web_results = await self.provider.search(search_query, limit=5)

            for item in web_results:
                url = item.get("url", "")
                title = item.get("title", "")
                if not url:
                    continue
                try:
                    scrape_result = await self.provider.scrape(url)
                    if scrape_result.get("success"):
                        markdown = scrape_result.get("data", {}).get("markdown", "")
                        option = self._parse_flight_from_markdown(
                            markdown, result_id, origin, destination, url, title,
                            depart_date, return_date
                        )
                        if option:
                            option.source_type = "search"
                            results.append(option)
                            result_id += 1
                except Exception:
                    pass
        except Exception:
            pass

        # Scrape aggregator sites (these often have better data)
        aggregator_results = await self._scrape_aggregator_sites(
            origin, destination, depart_date, return_date, result_id
        )
        results.extend(aggregator_results)

        # Filter and return results with valid prices
        valid_results = [r for r in results if r.price > 0.01]
        if valid_results:
            return valid_results

        results_with_url = [r for r in results if r.source_url]
        if results_with_url:
            return results_with_url

        return []

    async def _scrape_aggregator_sites(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str,
        start_id: int,
    ) -> List[TravelOption]:
        """Scrape flight aggregator websites."""
        results: List[TravelOption] = []
        result_id = start_id

        date_formats = self._parse_date_formats(depart_date)

        for site_name, base_url in AGGREGATOR_SITES:
            url = self._format_url(base_url, origin, destination, date_formats)

            try:
                scrape_result = await self.provider.scrape(url)
                if scrape_result.get("success"):
                    markdown = scrape_result.get("data", {}).get("markdown", "")
                    option = self._parse_flight_from_markdown(
                        markdown, result_id, origin, destination, url, site_name,
                        depart_date, return_date
                    )
                    if option:
                        option.source_type = "aggregator"
                        option.airline = site_name
                        results.append(option)
                        result_id += 1
            except Exception:
                results.append(self._make_fallback(
                    site_name, url, result_id, "aggregator", depart_date, return_date
                ))
                result_id += 1

        return results

    def _parse_date_formats(self, date_str: str) -> dict:
        """Parse date into various formats for URL templates."""
        if not date_str:
            return {}

        parts = date_str.split("-")
        if len(parts) == 3:
            year, month, day = parts[0], parts[1], parts[2]
            month_int = int(month) if month.startswith("0") else int(month)
            month_name = MONTH_NAMES[month_int - 1] if 1 <= month_int <= 12 else ""
            return {
                "date_iso": date_str,
                "date_dash": f"{month}-{day}",
                "date_slash": f"{month}/{day}",
                "date_us": f"{month}/{day}/{year}",
                "year": year,
                "month": month,
                "day": day,
                "month_name": month_name,
            }
        return {"date_iso": date_str}

    def _format_url(self, template: str, origin: str, destination: str, date_formats: dict) -> str:
        """Format URL template with origin, destination, and dates."""
        url = template
        url = url.replace("{origin}", origin.upper())
        url = url.replace("{destination}", destination.upper())

        for key, value in date_formats.items():
            url = url.replace(f"{{{key}}}", value)

        return url

    def _make_fallback(
        self,
        name: str,
        url: str,
        id: int,
        source_type: str,
        depart_date: str,
        return_date: str,
    ) -> TravelOption:
        """Create a fallback TravelOption with minimal data."""
        return TravelOption(
            id=id,
            airline=name,
            price=0.01,
            depart_time="--:--",
            arrival_time="--:--",
            duration="--",
            stops=0,
            source_url=url,
            source_type=source_type,
            depart_date=depart_date,
            return_date=return_date,
        )

    def _parse_flight_from_markdown(
        self,
        markdown: str,
        idx: int,
        origin: str,
        destination: str,
        source_url: str,
        title: str,
        depart_date: str,
        return_date: str,
    ) -> Optional[TravelOption]:
        """Parse flight information from markdown content."""
        airline = self._extract_airline(markdown, title)
        price = self._extract_price(markdown)
        depart_time = self._extract_time(markdown, "depart", depart_date)
        arrival_time = self._extract_time(markdown, "arrival", return_date or depart_date)
        duration = self._extract_duration(markdown)
        stops = self._extract_stops(markdown)

        if price == 0:
            price = 0.01

        return TravelOption(
            id=idx,
            airline=airline,
            price=price,
            depart_time=depart_time,
            arrival_time=arrival_time,
            duration=duration,
            stops=stops,
            source_url=source_url,
            source_type="search",
            depart_date=depart_date,
            return_date=return_date,
        )

    def _extract_airline(self, text: str, title: str = "") -> str:
        """Extract airline name from text."""
        airlines = [
            "American Airlines", "Delta", "United", "Southwest", "JetBlue", "Alaska",
            "Spirit", "Frontier", "Hawaiian", "Allegiant", "Virgin", "British Airways",
            "Lufthansa", "Air France", "KLM", "Emirates", "Qatar", "Singapore",
            "Cathay Pacific", "ANA", "Japan Airlines", "Qantas", "Air Canada",
            "Turkish", "Etihad", "Korean Air", "Asiana", "Thai Airways"
        ]

        text_lower = text.lower()
        title_lower = title.lower()

        for airline in airlines:
            if airline.lower() in title_lower:
                return airline

        for airline in airlines:
            if airline.lower() in text_lower:
                return airline

        return "Unknown"

    def _extract_price(self, text: str) -> float:
        """Extract price from text."""
        patterns = [
            r"\$([\d,]+\.?\d*)",
            r"price[:\s]+\$?([\d,]+\.?\d*)",
            r"from[:\s]+\$?([\d,]+\.?\d*)",
            r"([\d,]+\.?\d*)\s*(?:USD|\$)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    price_str = match.replace(",", "")
                    price = float(price_str)
                    if 0 < price < 100000:
                        return price
                except ValueError:
                    continue

        return 0.0

    def _extract_time(self, text: str, time_type: str, date_context: str = None) -> str:
        """Extract departure/arrival time from text."""
        time_pattern = r"(\d{1,2}:\d{2})\s*(?:AM|PM)?"
        all_times = re.findall(time_pattern, text, re.IGNORECASE)

        if all_times:
            if time_type == "depart":
                return all_times[0].upper()
            elif time_type == "arrival" and len(all_times) > 1:
                return all_times[1].upper()
            elif time_type == "arrival":
                return all_times[0].upper()

        return "08:00" if time_type == "depart" else "12:00"

    def _extract_duration(self, text: str) -> str:
        """Extract flight duration from text."""
        patterns = [
            r"duration[:\s]+(\d+h\s*\d*m?)",
            r"(\d+h\s*\d*m?)\s*(?:flight|duration)",
            r"(\d+\s*hr?\s*\d*\s*min?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "3h 30m"

    def _extract_stops(self, text: str) -> int:
        """Extract number of stops from text."""
        text_lower = text.lower()

        if "nonstop" in text_lower or "direct" in text_lower or "non-stop" in text_lower:
            return 0

        patterns = [
            r"(\d+)\s*stop",
            r"stop[:\s]+(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    pass

        return 0

    def _mock_results(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str,
    ) -> List[TravelOption]:
        """Return mock flight data for testing/fallback."""
        return [
            TravelOption(
                id=1,
                airline="SkyWings",
                price=299.99,
                depart_time="08:00",
                arrival_time="11:30",
                duration="3h 30m",
                stops=0,
                source_url="https://example.com/flights/skywings",
                source_type="airline",
                depart_date=depart_date,
                return_date=return_date,
            ),
            TravelOption(
                id=2,
                airline="AirConnect",
                price=199.50,
                depart_time="14:15",
                arrival_time="19:45",
                duration="5h 30m",
                stops=1,
                source_url="https://example.com/flights/airconnect",
                source_type="airline",
                depart_date=depart_date,
                return_date=return_date,
            ),
            TravelOption(
                id=3,
                airline="FastJet",
                price=349.00,
                depart_time="06:30",
                arrival_time="09:00",
                duration="2h 30m",
                stops=0,
                source_url="https://example.com/flights/fastjet",
                source_type="airline",
                depart_date=depart_date,
                return_date=return_date,
            ),
        ]