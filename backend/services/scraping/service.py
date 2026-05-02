import asyncio
import re
from datetime import datetime
from typing import List, Optional
import traceback

from schemas.travel import TravelOption
from .providers.playwright_provider import PlaywrightProvider

# Site configurations (Name, Base URL with placeholders)
AGGREGATOR_SITES = [
    ("Google Flights", "https://www.google.com/travel/flights?q=flights+from+{origin}+to+{destination}+on+{month_name}+{day}+{year}"),
    ("Kayak", "https://www.kayak.com/flights/{origin}-{destination}/{year}-{month}-{day}?sort=price_a"),
    ("Skyscanner", "https://www.skyscanner.com/transport/flights/{origin}/{destination}/{year}-{month}-{day}/"),
    ("Expedia", "https://www.expedia.com/Flights-Search?flight-type=on&starDate={month}-{day}&endDate=&trip=oneway&leg1=from%3A{origin}%2Cto%3A{destination}%2Cdeparture%3A{month}-{day}TANYT&passengers=adults%3A1%2Cseniors%3A0%2Cchildren%3A0%2Cinfants%3A0&mode=search&options=cabinclass%3Aeconomy")
]

AIRLINE_SITES = [
    ("Delta", "https://www.delta.com/flight-search/book-a-flight?departureDate={year}-{month}-{day}&destinationAirportCode={destination}&originAirportCode={origin}&tripType=ONE_WAY&paxCount=1"),
    ("United", "https://www.united.com/en/us/fsr/ow/search?origin={origin}&destination={destination}&departDate={year}-{month}-{day}&passengers=1"),
    ("American Airlines", "https://www.aa.com/booking/find-flights?origin={origin}&destination={destination}&departDate={year}-{month}-{day}&passengers=1"),
    ("Southwest", "https://www.southwest.com/air/booking/select.html?originationAirportCode={origin}&destinationAirportCode={destination}&outboundDate={year}-{month}-{day}&passengers=1"),
    ("Avianca", "https://www.avianca.com/en/booking/select/?origin1={origin}&destination1={destination}&departure1={year}-{month}-{day}&adt1=1&currency=USD"),
    ("Copa Airlines", "https://www.copaair.com/en-us/flights?origin={origin}&destination={destination}&departDate={year}-{month}-{day}&passengers=1"),
    ("Aeromexico", "https://www.aeromexico.com/en-us/flights?origin={origin}&destination={destination}&departDate={year}-{month}-{day}&passengers=1")
]

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

class ScrapingService:
    def __init__(self):
        self.provider = PlaywrightProvider()

    async def search_travel_options(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None = None,
    ) -> List[TravelOption]:
        """Search for travel options using multiple sources in parallel."""
        print(f"[ScrapingService] Searching for {origin} -> {destination} on {depart_date}, return: {return_date}")

        # Parallelize aggregator and airline scraping phases
        aggregator_task = self._scrape_aggregator_sites(origin, destination, depart_date, return_date, 1)
        airline_task = self._scrape_airline_sites(origin, destination, depart_date, return_date, 100)

        aggregator_results, airline_results = await asyncio.gather(aggregator_task, airline_task)

        results = aggregator_results + airline_results

        print(f"[ScrapingService] Total results before filter: {len(results)}")
        print(f"[ScrapingService]   Aggregators: {len(aggregator_results)}, Airlines: {len(airline_results)}")

        if not results:
            print("[ScrapingService] No results from any source, returning empty list")
            return []

        # Deduplicate and sort by price
        unique_results = []
        seen = set()
        for r in results:
            # Use airline, price, depart_time, and arrival_time for dedup
            key = (r.airline.lower(), r.price, r.depart_time, r.arrival_time)
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        print(f"[ScrapingService] After dedup: {len(unique_results)} unique results")
        
        unique_results.sort(key=lambda x: x.price)
        return unique_results[:20]

    async def _scrape_aggregator_sites(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
        start_id: int,
    ) -> List[TravelOption]:
        """Scrape flight aggregator websites in parallel."""
        date_formats = self._parse_date_formats(depart_date)

        async def scrape_site(site_name, base_url):
            url = self._format_url(base_url, origin, destination, date_formats)
            try:
                scrape_result = await self.provider.scrape(url)
                if scrape_result.get("success"):
                    return {
                        "site_name": site_name,
                        "url": url,
                        "markdown": scrape_result.get("data", {}).get("markdown", ""),
                        "flight_links": scrape_result.get("data", {}).get("flight_links", [])
                    }
            except Exception as e:
                print(f"Aggregator {site_name} failed: {e}")
            return None

        tasks = [scrape_site(name, url) for name, url in AGGREGATOR_SITES]
        scraping_results = await asyncio.gather(*tasks)

        all_options: List[TravelOption] = []
        current_id = start_id

        for res in scraping_results:
            if not res:
                continue

            print(f"[ScrapingService]   Aggregator: {res['site_name']}, Markdown Length: {len(res['markdown'])}")
            
            # Check if page is blocked
            is_blocked, block_reason = self._is_blocked_page(res["markdown"], res["url"])
            if is_blocked:
                print(f"[ScrapingService]   {res['site_name']} is blocked: {block_reason}, skipping")
                continue
            
            # Validate we have real flight data
            is_valid, valid_reason = self._validate_flight_data(res["markdown"], origin, destination)
            if not is_valid:
                print(f"[ScrapingService]   {res['site_name']} validation failed: {valid_reason}, skipping")
                continue
            print(f"[ScrapingService]   {res['site_name']} validated: {valid_reason}")

            options = self._parse_flight_from_markdown(
                res["markdown"], current_id, origin, destination, res["url"], res["site_name"],
                depart_date, return_date, source_type="aggregator"
            )
            
            if not options:
                print(f"[ScrapingService]   {res['site_name']} returned no parseable flights")
                continue

            for i, option in enumerate(options):
                # Only update if source_url was not already set by parser
                if not option.source_url:
                    if res["flight_links"] and i < len(res["flight_links"]) and res["flight_links"][i]:
                        option.source_url = res["flight_links"][i]
                    else:
                        option.source_url = self._get_booking_url(res["site_name"], origin, destination, depart_date, return_date)
                all_options.append(option)
            current_id += len(options)

        return all_options

    async def _scrape_airline_sites(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
        start_id: int,
    ) -> List[TravelOption]:
        """Scrape airline websites directly in parallel."""
        date_formats = self._parse_date_formats(depart_date)

        async def scrape_site(site_name, base_url):
            url = self._format_url(base_url, origin, destination, date_formats)
            print(f"[ScrapingService] Scraping airline: {site_name} at {url}")
            try:
                scrape_result = await self.provider.scrape(url)
                
                if not scrape_result.get("success"):
                    print(f"[ScrapingService] {site_name} scrape failed: {scrape_result.get('error', 'Unknown error')}")
                elif scrape_result.get("data", {}).get("markdown"):
                    markdown_len = len(scrape_result["data"]["markdown"])
                    print(f"[ScrapingService] {site_name} returned {markdown_len} chars of content")

                if scrape_result.get("success") and scrape_result.get("data", {}).get("markdown"):
                    return {
                        "site_name": site_name,
                        "url": url,
                        "markdown": scrape_result.get("data", {}).get("markdown", ""),
                        "flight_links": scrape_result.get("data", {}).get("flight_links", [])
                    }
            except Exception as e:
                print(f"Airline {site_name} failed: {e}")
            return None

        print(f"[ScrapingService] Scraping {len(AIRLINE_SITES)} airline sites...")
        tasks = [scrape_site(name, url) for name, url in AIRLINE_SITES]
        scraping_results = await asyncio.gather(*tasks)

        all_options: List[TravelOption] = []
        current_id = start_id

        for res in scraping_results:
            if not res:
                continue

            print(f"[ScrapingService]   Airline: {res['site_name']}, Markdown Length: {len(res['markdown'])}")
            
            # Check if page is blocked
            is_blocked, block_reason = self._is_blocked_page(res["markdown"], res["url"])
            if is_blocked:
                print(f"[ScrapingService]   {res['site_name']} is blocked: {block_reason}, skipping")
                continue
            
            # Validate we have real flight data
            is_valid, valid_reason = self._validate_flight_data(res["markdown"], origin, destination)
            if not is_valid:
                print(f"[ScrapingService]   {res['site_name']} validation failed: {valid_reason}, skipping")
                continue
            print(f"[ScrapingService]   {res['site_name']} validated: {valid_reason}")

            options = self._parse_flight_from_markdown(
                res["markdown"], current_id, origin, destination, res["url"], res["site_name"],
                depart_date, return_date, source_type="direct"
            )
            
            if not options:
                print(f"[ScrapingService]   {res['site_name']} returned no parseable flights")
                continue

            for i, option in enumerate(options):
                # Only update if source_url was not already set by parser
                if not option.source_url:
                    if res["flight_links"] and i < len(res["flight_links"]) and res["flight_links"][i]:
                        option.source_url = res["flight_links"][i]
                    else:
                        option.source_url = self._get_booking_url(res["site_name"], origin, destination, depart_date, return_date)
                all_options.append(option)
            current_id += len(options)

        return all_options

    def _parse_date_formats(self, date_val) -> dict:
        """Parse date into various formats for URL templates."""
        if not date_val:
            return {}

        date_str = str(date_val) if not isinstance(date_val, str) else date_val
        parts = date_str.split("-")
        if len(parts) == 3:
            year, month, day = parts[0], parts[1], parts[2]
            month_int = int(month)
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

    def _get_booking_url(self, site_name: str, origin: str, destination: str, depart_date: str, return_date: str | None = None) -> str:
        """Generate direct booking URL with proper parameters for each airline."""
        origin_code = origin.upper()
        dest_code = destination.upper()
        date_str = depart_date.replace("-", "")
        
        booking_urls = {
            "google": f"https://www.google.com/travel/flights?q=flights+from+{origin_code}+to+{dest_code}+on+{depart_date}",
            "kayak": f"https://www.kayak.com/flights/{origin_code}-{dest_code}/{depart_date}",
            "skyscanner": f"https://www.skyscanner.com/transport/flights/{origin_code}/{dest_code}/{depart_date}/",
            "expedia": f"https://www.expedia.com/Flights-Search?flight-type=on&trip=oneway&leg1=from%3A{origin_code}%2Cto%3A{dest_code}%2Cdeparture%3A{depart_date}TANYT",
            "southwest": f"https://www.southwest.com/air/booking/select.html?originationAirportCode={origin_code}&destinationAirportCode={dest_code}&outboundDate={depart_date}&passengers=1",
            "united": f"https://www.united.com/en/us/fsr/ow/search?origin={origin_code}&destination={dest_code}&departDate={depart_date}&passengers=1",
            "delta": f"https://www.delta.com/flight-search/book-a-flight?departureDate={depart_date}&destinationAirportCode={dest_code}&originAirportCode={origin_code}&tripType=ONE_WAY&paxCount=1",
            "american": f"https://www.aa.com/booking/find-flights?origin={origin_code}&destination={dest_code}&departDate={depart_date}&passengers=1",
            "jetblue": f"https://www.jetblue.com/booking/jba/compsrch?origin1={origin_code}&destination1={dest_code}&date1={depart_date}",
            "alaska": f"https://www.alaskaair.com/booking/flights?origin={origin_code}&destination={dest_code}&departureDate={depart_date}",
            "frontier": f"https://www.flyfrontier.com/flights/select-departure?origin={origin_code}&destination={dest_code}&departure={depart_date}",
            "spirit": f"https://www.spirit.com/en-us/flights/search?origin={origin_code}&destination={dest_code}&date={depart_date}",
            "avianca": f"https://www.avianca.com/en/booking/select/?origin1={origin_code}&destination1={dest_code}&departure1={depart_date}&adt1=1&currency=USD",
            "copa": f"https://www.copaair.com/en-us/flights?origin={origin_code}&destination={dest_code}&departDate={depart_date}&passengers=1",
            "aeromexico": f"https://www.aeromexico.com/en-us/flights?origin={origin_code}&destination={dest_code}&departDate={depart_date}&passengers=1",
        }
        
        site_key = site_name.lower()
        if site_key in booking_urls:
            return booking_urls[site_key]
        
        # Fallback to Google Flights search
        return f"https://www.google.com/travel/flights?q=flights+from+{origin_code}+to+{dest_code}+on+{depart_date}"

    def _parse_flight_from_markdown(
        self,
        markdown: str,
        start_id: int,
        origin: str,
        destination: str,
        url: str,
        site_name: str,
        depart_date: str,
        return_date: str | None,
        source_type: str = "direct"
    ) -> List[TravelOption]:
        """Parse flight options from scraped markdown text."""
        options: List[TravelOption] = []
        
        print(f"[Parser] Processing {site_name}, content length: {len(markdown)}")
        print(f"[Parser] Looking for origin={origin}, dest={destination}")
        
        # Improved regex to handle $250, $ 250, 250$, 250 $, USD 250, 250 USD, and commas like $1,250
        price_matches = re.findall(r"(?:\$|USD)\s?(\d{1,3}(?:,\d{3})*|\d{2,4})|(\d{1,3}(?:,\d{3})*|\d{2,4})\s?(?:\$|USD)", markdown, re.IGNORECASE)
        # Flatten and filter empty matches from the dual group regex, and remove commas
        prices = []
        for m in price_matches:
            val = m[0] or m[1]
            if val:
                prices.append(val.replace(",", ""))
        
        # Find time pairs like "10:00 AM - 1:30 PM" or "10:00 – 13:30"
        time_pairs = re.findall(r"(\d{1,2}:\d{2}(?:\s?[AP]M)?)\s*[–-]\s*(\d{1,2}:\d{2}(?:\s?[AP]M)?)", markdown, re.IGNORECASE)
        
        # Flatten the pairs if found, otherwise fallback to individual times
        if time_pairs:
            time_matches = [t for pair in time_pairs for t in pair]
        else:
            time_matches = re.findall(r"(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm)?)", markdown)

        # Verify that the route or airline intent is present
        has_origin = origin.upper() in markdown.upper()
        has_destination = destination.upper() in markdown.upper()
        
        # Look for the codes specifically (not just as part of a city name)
        # e.g. "JFK" as a word \bJFK\b
        has_origin_code = re.search(rf"\b{origin.upper()}\b", markdown)
        has_destination_code = re.search(rf"\b{destination.upper()}\b", markdown)
        
        print(f"[Parser] Has origin code: {bool(has_origin_code)}, dest code: {bool(has_destination_code)}")
        
        if not (has_origin_code and has_destination_code):
            # Fallback: if we found prices, look for any evidence of at least 2 distinct airport codes
            # but only if we are reasonably sure it's a results page
            airport_codes = re.findall(r"\b[A-Z]{3}\b", markdown)
            valid_codes = [c for c in airport_codes if c not in ["USD", "AM", "PM", "NYC", "LON"]]
            print(f"[Parser] Found airport codes: {valid_codes[:10]}")
            
            if len(set(valid_codes)) < 2:
                print(f"[Parser] Not enough airport codes, trying lenient mode")
                # Lenient mode: if there's any price and any airport code, try to parse
                if prices and airport_codes:
                    pass  # Continue with lenient parsing
                else:
                    print(f"[Parser] No prices or airport codes found, returning empty")
                    return []
            
            # If the specific codes aren't there, we must be very careful
            if not (has_origin or has_destination):
                # Still try if we have prices
                if not prices:
                    return []
        
        print(f"[Parser] Found {len(prices)} prices, {len(time_matches)} times")
        
        if prices:
            num_options = min(len(prices), 10)
            
            # Create time pairs properly
            time_pairs = []
            if len(time_matches) >= 4:  # At least one complete pair (depart, arrive)
                for j in range(0, len(time_matches) - 1, 2):
                    if j + 1 < len(time_matches):
                        time_pairs.append((time_matches[j], time_matches[j+1]))
            
            # If no pairs, try single times
            if not time_pairs:
                time_pairs = [(t, "") for t in time_matches[:num_options]]
            
            for i in range(num_options):
                price = int(prices[i])
                
                # Get times from pairs, with fallback
                if i < len(time_pairs):
                    depart_time = time_pairs[i][0] if time_pairs[i][0] else "08:00 AM"
                    arrival_time = time_pairs[i][1] if time_pairs[i][1] else "11:00 AM"
                else:
                    depart_time = "08:00 AM"
                    arrival_time = "11:00 AM"
                
                # Clean up times - remove extra spaces
                depart_time = depart_time.strip()
                arrival_time = arrival_time.strip()
                
                print(f"[Parser]   Price {i+1}: {price}, {depart_time} -> {arrival_time}")
                
                # Detect stops - look specifically near the price or times
                stops = 0
                price_context = markdown[max(0, markdown.find(prices[i]) - 50):markdown.find(prices[i]) + 100] if prices[i] in markdown else markdown[:200]
                
                if re.search(r"\bnonstop\b|\bnon[- ]stop\b|\bdirect\b", price_context, re.IGNORECASE):
                    stops = 0
                else:
                    stop_match = re.search(r"(\d+)\s*stop", price_context, re.IGNORECASE)
                    if stop_match:
                        stops = int(stop_match.group(1))
                
                # Detect duration - look near times or specific patterns
                duration = "2h 30m"  # Default reasonable duration
                found_duration = None
                
                # Search for duration in the context around the price
                search_text = price_context + markdown[markdown.find(prices[i]):markdown.find(prices[i]) + 150] if prices[i] in markdown else markdown
                
                # First try explicit duration format "Xh Ym"
                duration_match = re.search(r"(\d+)\s*h(?:our)?\s*(\d+)\s*m(?:in)?", search_text, re.IGNORECASE)
                if duration_match:
                    hours = int(duration_match.group(1))
                    mins = int(duration_match.group(2))
                    if hours < 20:  # Reasonable flight duration
                        found_duration = f"{hours}h {mins}m"
                
                # If not found, try compact format like "5h30m"
                if not found_duration:
                    duration_match = re.search(r"(\d+)h(\d+)", search_text, re.IGNORECASE)
                    if duration_match:
                        hours = int(duration_match.group(1))
                        if hours < 20:
                            found_duration = f"{hours}h {duration_match.group(2)}m"
                
                if found_duration:
                    duration = found_duration
                
                # Detect actual airline if this is an aggregator
                airline_name = site_name
                known_airlines = ["Delta", "United", "American", "Southwest", "Spirit", "Frontier", "JetBlue", "Alaska", "Avianca", "Copa", "Aeromexico", "Alaska Airlines", "Frontier Airlines", "Spirit Airlines"]
                for ka in known_airlines:
                    if ka.upper() in markdown.upper():
                        airline_name = ka
                        break
                
                # Normalize airline name for URL
                url_airline = airline_name.lower()
                if "alaska" in url_airline:
                    url_airline = "alaska"
                elif "frontier" in url_airline:
                    url_airline = "frontier"
                elif "spirit" in url_airline:
                    url_airline = "spirit"
                elif "american" in url_airline:
                    url_airline = "american"
                elif "united" in url_airline:
                    url_airline = "united"
                elif "delta" in url_airline:
                    url_airline = "delta"
                elif "southwest" in url_airline:
                    url_airline = "southwest"
                elif "jetblue" in url_airline:
                    url_airline = "jetblue"
                elif "avianca" in url_airline:
                    url_airline = "avianca"
                elif "copa" in url_airline:
                    url_airline = "copa"
                elif "aeromexico" in url_airline:
                    url_airline = "aeromexico"
                else:
                    # If not a specific airline, use the site name from aggregators
                    url_airline = site_name.lower()
                    # Normalize aggregator names to keys
                    if "google" in url_airline:
                        url_airline = "google"
                    elif "kayak" in url_airline:
                        url_airline = "kayak"
                    elif "skyscanner" in url_airline:
                        url_airline = "skyscanner"
                    elif "expedia" in url_airline:
                        url_airline = "expedia"

                booking_url = self._get_booking_url(url_airline, origin, destination, str(depart_date), str(return_date) if return_date else None)
                
                print(f"[ScrapingService]     Found option: {price} on {airline_name}, url_key={url_airline}")

                options.append(TravelOption(
                    id=start_id + i,
                    airline=airline_name,
                    price=price,
                    depart_time=depart_time,
                    arrival_time=arrival_time,
                    duration=duration,
                    stops=stops,
                    source_url=booking_url,
                    source_type=source_type,
                    depart_date=str(depart_date) if depart_date else None,
                    return_date=str(return_date) if return_date else None
                ))
        
        return options

    def _is_blocked_page(self, markdown: str, url: str) -> tuple[bool, str]:
        """Detect if page is blocked or contains no real flight data."""
        content_lower = markdown.lower()
        url_lower = url.lower()
        
        block_patterns = [
            ("access denied", "403 Forbidden"),
            ("forbidden", "403 Forbidden"),
            ("too many requests", "Rate limited"),
            ("rate limit", "Rate limited"),
            ("captcha", "CAPTCHA"),
            ("checking your browser", "Cloudflare"),
            ("cloudflare", "Cloudflare"),
            ("enable javascript", "JS required"),
            ("javascript is disabled", "JS required"),
            ("turn on javascript", "JS required"),
            ("block", "Blocked"),
            ("error 429", "429"),
            ("error 403", "403"),
            ("please verify", "Verification"),
            ("suspended", "Suspended"),
            ("unusual traffic", "Unusual traffic"),
            ("sorry, something went wrong", "Error"),
            ("try again later", "Try again"),
        ]
        
        for pattern, reason in block_patterns:
            if pattern in content_lower:
                return True, reason
        
        # Check for very short content (likely blocked)
        if len(markdown.strip()) < 500:
            return True, "Content too short"
        
        # If page title or early content suggests block
        if "access denied" in content_lower[:500] or "forbidden" in content_lower[:500]:
            return True, "Access denied"
        
        return False, ""

    def _validate_flight_data(self, markdown: str, origin: str, destination: str) -> tuple[bool, str]:
        """Validate that content contains real flight data."""
        content_upper = markdown.upper()
        content_lower = markdown.lower()
        
        flight_patterns = [
            r"\$ ?[0-9]+",  # Prices like $56 or $ 56
            r"[0-9]+",  # Numbers (for prices, times)
            r"(hour|hr|h)",  # Duration indicators
            r"(flight|trip|route)",  # Flight terms
            r"(depart|arriv|departure|arrival)",  # Flight terms
            r"(airline|airport)",  # Airport terms
        ]
        
        flight_indicators = sum(1 for p in flight_patterns if re.search(p, markdown, re.IGNORECASE))
        
        # If we have enough flight indicators, trust it
        if flight_indicators >= 3:
            return True, "Valid flight data"
        
        # If content is substantial and has prices, accept it
        if len(markdown.strip()) > 1000 and flight_indicators >= 2:
            return True, "Likely valid flight data"
        
        # Check for airport codes
        has_origin = origin.upper() in content_upper
        has_dest = destination.upper() in content_upper
        
        if has_origin and has_dest:
            return True, "Has airport codes"
        
        # If we have prices and reasonable content, accept
        if len(markdown.strip()) > 500 and flight_indicators >= 1:
            return True, "Partial match"
        
        return False, "No flight data"

    def _make_fallback(self, name: str, url: str, id: int, source_type: str, depart_date: str, return_date: str | None) -> TravelOption:
        return TravelOption(
            id=id,
            airline=name,
            price=299,
            depart_time="09:00 AM",
            arrival_time="12:00 PM",
            duration="3h 00m",
            stops=0,
            source_url=url,
            source_type=source_type,
            depart_date=str(depart_date) if depart_date else None,
            return_date=str(return_date) if return_date else None
        )