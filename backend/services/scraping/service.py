import os

import anyio
from anyio.abc import ObjectSendStream
from concurrency import gather
import re
from datetime import datetime
from typing import Any, AsyncIterator, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
import traceback

from schemas.travel import TravelOption
from .carriers import (
    find_airline_in_text,
    match_airline_from_operated_by,
    match_airline_name,
)
from .providers import get_provider
from .ai_parser import AIParser, _normalize_time_12h

# Site configurations (Name, Base URL with placeholders)
AGGREGATOR_SITES = [
    (
        "Google Flights",
        "https://www.google.com/travel/flights?q=flights+from+{origin}+to+{destination}"
        "+on+{month_name}+{day}+{year}&hl=en&gl=us&curr=USD",
    ),
    (
        "Kayak",
        "https://www.kayak.com/flights/{origin}-{destination}/{year}-{month}-{day}"
        "?sort=price_a&currency=USD",
    ),
    (
        "Skyscanner",
        "https://www.skyscanner.com/transport/flights/{origin}/{destination}/"
        "{year}-{month}-{day}/?currency=USD&market=US&locale=en-US",
    ),
    (
        "Expedia",
        "https://www.expedia.com/Flights-Search?flight-type=on&starDate={month}-{day}"
        "&endDate=&trip=oneway&leg1=from%3A{origin}%2Cto%3A{destination}%2Cdeparture%3A"
        "{month}-{day}TANYT&passengers=adults%3A1%2Cseniors%3A0%2Cchildren%3A0%2Cinfants%3A0"
        "&mode=search&options=cabinclass%3Aeconomy&locale=en_US&currency=USD",
    ),
]

# Currency/locale on scrape URLs — pages should return USD; parsers match $ / USD in text.
_AGGREGATOR_CURRENCY_QUERY: dict[str, dict[str, str]] = {
    "google.com": {"hl": "en", "gl": "us", "curr": "USD"},
    "kayak.com": {"currency": "USD"},
    "skyscanner.com": {"currency": "USD", "market": "US", "locale": "en-US"},
    "expedia.com": {"locale": "en_US", "currency": "USD"},
}

# Canonical booking URL patterns (match each carrier’s live site query strings).
AIRLINE_SITES = [
    (
        "Delta",
        "https://www.delta.com/flight-search/book-a-flight?"
        "departureDate={date_iso}&destinationAirportCode={destination}"
        "&originAirportCode={origin}&tripType=ONE_WAY&paxCount=1",
    ),
    (
        "United",
        "https://www.united.com/en/us/fsr/ow/search?"
        "origin={origin}&destination={destination}&departDate={date_iso}&passengers=1",
    ),
    (
        "American Airlines",
        "https://www.aa.com/booking/find-flights?"
        "origin={origin}&destination={destination}&departDate={date_iso}&passengers=1",
    ),
    (
        "Southwest",
        "https://www.southwest.com/air/booking/select.html?"
        "originationAirportCode={origin}&destinationAirportCode={destination}"
        "&outboundDate={date_iso}&adultPassengersCount=1",
    ),
    (
        "Avianca",
        "https://www.avianca.com/en/booking/select/?"
        "origin1={origin}&destination1={destination}&departure1={date_iso}"
        "&adt1=1&currency=USD",
    ),
    (
        "Copa Airlines",
        "https://www.copaair.com/en-us/flights?"
        "origin={origin}&destination={destination}&departDate={date_iso}&passengers=1",
    ),
    (
        "Aeromexico",
        "https://www.aeromexico.com/en-us/flights?"
        "origin={origin}&destination={destination}&departDate={date_iso}&passengers=1",
    ),
]

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

# Built-in search scope — all aggregators and airlines, no .env toggles required.
_SEARCH_TIMEOUT_SEC = 240.0
_AGGREGATOR_SCRAPE_TIMEOUT_SEC = 50.0
_AIRLINE_SCRAPE_TIMEOUT_SEC = 90.0
_AIRLINE_BATCH_SIZE = 2
_SCRAPE_CONCURRENCY = 3
_scrape_slot = anyio.Semaphore(_SCRAPE_CONCURRENCY)
_AI_TIMEOUT_SEC = 20.0
_MAX_FLIGHTS_PER_SCRAPE = 100
_AIRLINE_COMPANION_ID_OFFSET = 900_000
_AI_CONTENT_MAX_CHARS = 6_000
_AI_MAX_ROW_SNIPPETS = 15

# Fare amounts as shown on USD result pages (no post-scrape currency conversion).
_USD_PRICE_CAPTURE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")
_ROW_BLOCK_RE = re.compile(
    r"--- Row \d+ ---\s*\n(.*?)(?=\n--- Row \d+ ---|\n--- Full page text|\Z)",
    re.DOTALL,
)
_AGGREGATOR_OFFER_PRICE_RE = re.compile(
    r"(?:from\s+)?(?:US\$|\$|USD)\s*([\d,]+(?:\.\d{2})?)\s*\*?",
    re.IGNORECASE,
)

_AIRLINE_SITE_NAMES = frozenset(name for name, _ in AIRLINE_SITES)

_AIRLINE_BOOKING_DOMAINS = (
    "delta.com",
    "united.com",
    "aa.com",
    "southwest.com",
    "avianca.com",
    "copaair.com",
    "aeromexico.com",
    "jetblue.com",
    "alaskaair.com",
    "spirit.com",
    "frontier.com",
)

_PRICE_SIGNAL_RE = re.compile(r"\$\s*[\d,]+(?:\.\d{2})?")

_MIN_FARE_USD = 50
_MAX_FARE_USD = 15_000

_GOOGLE_ROUNDTRIP_PRICE_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d{2})?)\s*(?:\r?\n\s*)?round\s*trip\b",
    re.IGNORECASE,
)
_GOOGLE_ONEWAY_PRICE_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d{2})?)\s*(?:\r?\n\s*)?(?:one-?way|per traveler)\b",
    re.IGNORECASE,
)

_AGGREGATOR_SITE_NAMES = frozenset(name for name, _ in AGGREGATOR_SITES)


def _route_codes_in_text(text: str, origin: str, destination: str) -> bool:
    """True when snippet looks like a flight card for this origin→destination."""
    o, d = origin.upper(), destination.upper()
    upper = text.upper()
    if o not in upper or d not in upper:
        return False
    for sep in ("–", "-", "—", " to "):
        if f"{o}{sep}{d}" in upper:
            return True
    o_pos = upper.rfind(o)
    d_pos = upper.rfind(d)
    return o_pos >= 0 and d_pos >= 0 and abs(o_pos - d_pos) <= 120


_CARD_LINE_SKIP_RE = re.compile(
    r"^\s*("
    r"\$|usd|\d{1,2}:\d{2}|\d{1,2}\s*[ap]\.?m\.?|round\s*trip|one-?way|"
    r"nonstop|non-stop|\d+\s*stop|stop\(|layover|\d+\s*hr|hour|min|"
    r"bags?|emissions?|co2|carbon|\bkg\b|cheapest|best\b|top\s|filter|price|duration|"
    r"depart|arriv|flight\s*#|\+\d|google|kayak|skyscanner|expedia|"
    r"to\s+update|update\s+prices?|click\s+to|select\s+flight"
    r")\b",
    re.IGNORECASE,
)
_MARKETING_LINE_RE = re.compile(
    r"book flights|cheap flights|flights with|from usd|discover .{0,40} destinations|"
    r"offers on flights|subscribe and save|skip to content|each --- row|"
    r"full page text|viewed \d+ .+ ago|round trip\s*/\s*economy|book now|"
    r"^\*|restrictions apply|terms & conditions|our app|popular flights",
    re.IGNORECASE,
)
def _is_marketing_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return True
    if _MARKETING_LINE_RE.search(stripped):
        return True
    if re.search(r"from\s+usd\s*\d", stripped, re.I):
        return True
    return False


def _is_valid_carrier_name(name: str | None) -> bool:
    """True only when name matches a known airline."""
    return match_airline_name(name or "") is not None


def _strip_marketing_header(markdown: str) -> str:
    """Drop page title / hero copy so it is not parsed as airline or fare rows."""
    lines = markdown.splitlines()
    cleaned: list[str] = []
    for line in lines:
        if not cleaned and _is_marketing_line(line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _extract_carrier_label_from_card(snippet: str, route_end: int) -> str | None:
    """Known airline from 'operated by' or a card line above the route."""
    card = snippet[max(0, route_end - 380) : route_end]
    matched = match_airline_from_operated_by(card)
    if matched:
        return matched

    for line in reversed([ln.strip() for ln in card.splitlines() if ln.strip()]):
        matched = match_airline_name(line)
        if matched:
            return matched
    return None


def _carrier_from_itinerary_snippet(
    snippet: str,
    default: str,
    origin: str = "",
    destination: str = "",
) -> str | None:
    """Operating carrier for one itinerary card, or None if not identifiable."""
    if not snippet.strip():
        return default if default not in _AGGREGATOR_SITE_NAMES else None

    upper = snippet.upper()
    route_end = len(snippet)
    if origin and destination:
        o, d = origin.upper(), destination.upper()
        for sep in ("–", "-", "—"):
            marker = f"{o}{sep}{d}"
            pos = upper.rfind(marker)
            if pos >= 0:
                route_end = min(route_end, pos + len(marker))

    near = snippet[max(0, route_end - 220) : route_end]
    found = find_airline_in_text(near)
    if found:
        return found

    wide = snippet[max(0, route_end - 450) : route_end]
    filter_sidebar = sum(
        1 for name in ("American", "United", "Delta", "Southwest", "JetBlue")
        if name.upper() in wide.upper()
    ) >= 4
    if not filter_sidebar:
        found = find_airline_in_text(wide)
        if found:
            return found

    label = _extract_carrier_label_from_card(snippet, route_end)
    if label:
        return label

    if not filter_sidebar:
        found = find_airline_in_text(snippet)
        if found:
            return found

    matched_default = match_airline_name(default)
    if matched_default:
        return matched_default
    return None


def _finalize_carrier_name(
    carrier: str | None,
    site_name: str,
    source_type: str,
) -> str | None:
    matched = match_airline_name(carrier or "")
    if matched:
        return matched
    site_airline = match_airline_name(site_name)
    if source_type == "airline" and site_name in _AIRLINE_SITE_NAMES:
        return site_airline or site_name
    if source_type == "aggregator" and site_name in _AGGREGATOR_SITE_NAMES:
        return site_name
    return None


def _append_query_params(url: str, params: dict[str, str]) -> str:
    """Merge query params into URL without overwriting existing keys."""
    if not params:
        return url
    parsed = urlparse(url)
    existing = parse_qs(parsed.query, keep_blank_values=True)
    existing_lower = {k.lower() for k in existing}
    for key, value in params.items():
        if key.lower() not in existing_lower:
            existing[key] = [value]
    query = urlencode(existing, doseq=True)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)
    )


def _apply_aggregator_usd_locale(url: str) -> str:
    """Merge USD/locale query params from _AGGREGATOR_CURRENCY_QUERY into scrape URLs."""
    low = url.lower()
    for host, params in _AGGREGATOR_CURRENCY_QUERY.items():
        if host in low:
            return _append_query_params(url, params)
    return url


def _markdown_with_row_texts(res: dict) -> str:
    """Merge Playwright per-row snippets into markdown for parsing."""
    md = res.get("markdown", "") or ""
    rows = res.get("flight_row_texts") or []
    if not rows:
        return md
    blocks = "\n".join(f"--- Row {i + 1} ---\n{t}" for i, t in enumerate(rows) if t)
    return f"{md}\n\n{blocks}" if md else blocks


def _excerpt_fare_regions(markdown: str, max_chars: int = _AI_CONTENT_MAX_CHARS) -> str:
    """Small windows around $prices for AI fallback (not the full page)."""
    if not markdown:
        return ""
    chunks: list[str] = []
    seen: set[int] = set()
    for match in _USD_PRICE_CAPTURE_RE.finditer(markdown):
        start = max(0, match.start() - 450)
        if start in seen:
            continue
        seen.add(start)
        end = min(len(markdown), match.end() + 100)
        chunks.append(markdown[start:end].strip())
        if sum(len(c) for c in chunks) >= max_chars:
            break
    if chunks:
        return "\n\n---\n\n".join(chunks)[:max_chars]
    return markdown[:max_chars]


def _markdown_for_ai(res: dict, origin: str = "", destination: str = "") -> str:
    """Minimal text for AI — row blocks or fare excerpts only (saves tokens)."""
    header = ""
    if origin and destination:
        header = f"Route: {origin.upper()} -> {destination.upper()}\n\n"

    rows = [t.strip() for t in (res.get("flight_row_texts") or []) if t and len(t.strip()) >= 15]
    if not rows:
        md = res.get("markdown", "") or ""
        rows = [
            b.strip()
            for b in _ROW_BLOCK_RE.findall(md)
            if len(b.strip()) >= 15
        ]

    if rows:
        parts = [f"--- Row {i + 1} ---\n{rows[i]}" for i in range(min(len(rows), _AI_MAX_ROW_SNIPPETS))]
        body = "\n\n".join(parts)
        return (header + body)[:_AI_CONTENT_MAX_CHARS]

    md = res.get("markdown", "") or ""
    return (header + _excerpt_fare_regions(md))[:_AI_CONTENT_MAX_CHARS]


def _build_scrape_payload(
    site_name: str,
    url: str,
    data: dict,
    *,
    origin: str = "",
    destination: str = "",
) -> dict:
    """Normalize Playwright scrape data for parsing (aggregators and airlines)."""
    markdown = _strip_marketing_header(data.get("markdown", "") or "")
    if origin and destination:
        route_header = (
            f"Search route: {origin.upper()} to {destination.upper()}\n\n"
        )
        if route_header.strip() not in markdown[:80]:
            markdown = route_header + markdown
    return {
        "site_name": site_name,
        "url": url,
        "markdown": markdown,
        "flight_links": data.get("flight_links", []),
        "flight_row_texts": data.get("flight_row_texts", []),
        "page_url": data.get("page_url") or data.get("url") or url,
        "page_title": data.get("page_title", "") or data.get("title", ""),
        "response_status": data.get("response_status"),
    }


def _option_source_host(opt: TravelOption) -> str:
    if not opt.source_url:
        return ""
    try:
        return urlparse(opt.source_url).netloc.lower()
    except Exception:
        return ""


def _dedupe_options(options: list[TravelOption]) -> list[TravelOption]:
    unique: list[TravelOption] = []
    seen: set[tuple] = set()
    for opt in options:
        key = (
            opt.source_type,
            _option_source_host(opt),
            opt.airline.lower(),
            round(opt.price, 2),
            opt.depart_time,
            opt.arrival_time,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(opt)
    unique.sort(
        key=lambda x: (
            0 if x.source_type == "aggregator" else 1,
            x.price if x.price > 0 else 99999,
            x.airline,
        )
    )
    return unique


def _is_plausible_flight_booking_link(link: str, page_url: str) -> bool:
    if not link or not link.startswith("http"):
        return False
    low = link.lower()
    if any(
        x in low
        for x in (
            "/flights/",
            "flight-search",
            "find-flights",
            "book-a-flight",
            "fsr/",
            "transport/flights",
            "flights-search",
            "air/booking",
        )
    ):
        return True
    try:
        return urlparse(link).netloc == urlparse(page_url).netloc and (
            "flight" in low or "book" in low or "select" in low
        )
    except Exception:
        return False


def _is_airline_booking_domain(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(domain in host for domain in _AIRLINE_BOOKING_DOMAINS)


class ScrapingService:
    def __init__(self):
        self.provider = get_provider()
        self.ai_parser = AIParser()
        self.source_status: dict[str, str] = {}
        self._reset_source_status()

    def _reset_source_status(self):
        """Reset per-request source tracking."""
        self.source_status = {}
        self._blocked_sources: list[str] = []
        self._failed_sources: list[str] = []
        self._ok_sources: list[str] = []

    def _mark_source(self, site_name: str, status: str):
        self.source_status[site_name] = status
        if status.startswith("blocked"):
            self._blocked_sources.append(site_name)
        elif status.startswith("error"):
            self._failed_sources.append(site_name)
        elif status == "ok":
            self._ok_sources.append(site_name)

    async def search_travel_options(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None = None,
    ) -> List[TravelOption]:
        """Search for travel options using multiple sources in parallel."""
        try:
            with anyio.fail_after(_SEARCH_TIMEOUT_SEC):
                return await self._search_travel_options_impl(
                    origin, destination, depart_date, return_date
                )
        except TimeoutError:
            print(
                f"[ScrapingService] Search timed out after {_SEARCH_TIMEOUT_SEC}s "
                f"({origin} -> {destination})"
            )
            return self._make_search_fallbacks(
                origin, destination, depart_date, return_date, reason="timeout"
            )

    async def _search_travel_options_impl(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None = None,
    ) -> List[TravelOption]:
        self._reset_source_status()
        print(f"[ScrapingService] Searching for {origin} -> {destination} on {depart_date}, return: {return_date}")

        print(
            f"[ScrapingService] Scraping {len(AGGREGATOR_SITES)} aggregator(s) and "
            f"{len(AIRLINE_SITES)} airline site(s) in parallel"
        )
        aggregator_results, airline_results = await gather(
            self._scrape_aggregator_sites(
                origin, destination, depart_date, return_date, 1
            ),
            self._scrape_airline_sites(
                origin, destination, depart_date, return_date, 100_000
            ),
        )

        results = aggregator_results + airline_results

        print(f"[ScrapingService] Total results before filter: {len(results)}")
        print(f"[ScrapingService]   Aggregators: {len(aggregator_results)}, Airlines: {len(airline_results)}")
        print(f"[ScrapingService]   Source status: {self.source_status}")

        if results:
            unique_results = _dedupe_options(results)
            print(f"[ScrapingService] After dedup: {len(unique_results)} unique results")
            return unique_results

        print("[ScrapingService] No parsed results from any source")
        return self._make_search_fallbacks(
            origin, destination, depart_date, return_date, reason="no_results"
        )

    async def _fetch_aggregator_raw_timed(
        self,
        site_name: str,
        base_url: str,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
    ) -> dict | None:
        return await self._run_timed_scrape(
            site_name,
            self._fetch_aggregator_raw(
                site_name, base_url, origin, destination, depart_date, return_date
            ),
            _AGGREGATOR_SCRAPE_TIMEOUT_SEC,
        )

    async def _run_timed_scrape(
        self,
        site_name: str,
        coro,
        timeout_sec: float,
    ) -> dict | None:
        """Run scrape with slot limit so queue time does not eat the timeout."""
        async with _scrape_slot:
            try:
                with anyio.fail_after(timeout_sec):
                    return await coro
            except TimeoutError:
                print(
                    f"[ScrapingService] {site_name} scrape timed out after "
                    f"{timeout_sec}s"
                )
                self._mark_source(site_name, "error:timeout")
                return None

    @staticmethod
    def _serialize_options(options: list[TravelOption]) -> list[dict[str, Any]]:
        return [o.model_dump(mode="json") for o in options]

    async def search_travel_stream(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield partial results as each aggregator finishes; fallbacks only if none return fares."""
        self._reset_source_status()
        print(
            f"[ScrapingService] Stream search {origin} -> {destination} on {depart_date}"
        )

        next_id = 1000
        had_fares = False

        async def scrape_one(site_name: str, base_url: str) -> tuple[str, list[TravelOption]]:
            nonlocal next_id
            raw = await self._fetch_aggregator_raw_timed(
                site_name, base_url, origin, destination, depart_date, return_date
            )
            if not raw:
                self._mark_source(site_name, "error:scrape_failed")
                return site_name, []
            options, next_id = await self._process_aggregator_payload(
                raw,
                next_id,
                origin,
                destination,
                depart_date,
                return_date,
                fast_parse=False,
            )
            return site_name, options

        async def scrape_airline_one(site_name: str, base_url: str) -> tuple[str, list[TravelOption]]:
            stride = 10000
            idx = next(
                (i for i, (n, _) in enumerate(AIRLINE_SITES) if n == site_name),
                0,
            )
            id_start = 200_000 + idx * stride
            raw = await self._fetch_airline_raw_timed(
                site_name, base_url, origin, destination, depart_date, return_date
            )
            if not raw:
                return site_name, []
            options, _ = await self._process_airline_payload(
                raw,
                id_start,
                origin,
                destination,
                depart_date,
                return_date,
                fast_parse=False,
            )
            return site_name, options

        send_stream, receive_stream = anyio.create_memory_object_stream[
            tuple[str, list[TravelOption]]
        ](0)

        async def run_scrapers() -> None:
            try:
                async with anyio.create_task_group() as tg:
                    for name, url in AGGREGATOR_SITES:
                        tg.start_soon(_stream_scrape_one, name, url, send_stream)
                    for name, url in AIRLINE_SITES:
                        tg.start_soon(_stream_scrape_airline_one, name, url, send_stream)
            finally:
                await send_stream.aclose()

        async def _stream_scrape_one(
            site_name: str,
            base_url: str,
            stream: ObjectSendStream[tuple[str, list[TravelOption]]],
        ) -> None:
            try:
                result = await scrape_one(site_name, base_url)
                await stream.send(result)
            except Exception as exc:
                print(f"[ScrapingService] Stream task {site_name} failed: {exc}")
                self._mark_source(site_name, f"error:{exc}")

        async def _stream_scrape_airline_one(
            site_name: str,
            base_url: str,
            stream: ObjectSendStream[tuple[str, list[TravelOption]]],
        ) -> None:
            try:
                result = await scrape_airline_one(site_name, base_url)
                await stream.send(result)
            except Exception as exc:
                print(f"[ScrapingService] Stream task {site_name} failed: {exc}")
                self._mark_source(site_name, f"error:{exc}")

        async with anyio.create_task_group() as tg:
            tg.start_soon(run_scrapers)
            try:
                with anyio.fail_after(_SEARCH_TIMEOUT_SEC):
                    async with receive_stream:
                        async for source, options in receive_stream:
                            if options:
                                had_fares = True
                                yield {
                                    "event": "chunk",
                                    "options": self._serialize_options(options),
                                    "source": source,
                                    "done": False,
                                }
            except TimeoutError:
                pass

        if not had_fares:
            extra = self._make_search_fallbacks(
                origin, destination, depart_date, return_date, reason="no_results"
            )
            if extra:
                yield {
                    "event": "chunk",
                    "options": self._serialize_options(extra),
                    "source": "fallback",
                    "done": False,
                }

        yield {
            "event": "done",
            "source_status": dict(self.source_status),
            "done": True,
        }

    async def _fetch_aggregator_raw(
        self,
        site_name: str,
        base_url: str,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None = None,
    ) -> dict | None:
        url = self._build_aggregator_url(
            base_url, origin, destination, depart_date, return_date
        )
        try:
            scrape_result = await self.provider.scrape(url)
            if scrape_result.get("success"):
                data = scrape_result.get("data") or {}
                return _build_scrape_payload(
                    site_name, url, data, origin=origin, destination=destination
                )
        except Exception as e:
            print(f"Aggregator {site_name} failed: {e}")
        return None

    async def _scrape_aggregator_sites(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
        start_id: int,
    ) -> List[TravelOption]:
        """Scrape and parse flight aggregator websites — all in parallel."""
        print(f"[ScrapingService] Scraping {len(AGGREGATOR_SITES)} aggregator(s)")

        scrape_tasks = [
            self._fetch_aggregator_raw_timed(
                name, url, origin, destination, depart_date, return_date
            )
            for name, url in AGGREGATOR_SITES
        ]
        scraping_results = await gather(*scrape_tasks)

        stride = 10000
        parse_tasks = []
        for idx, ((name, _), res) in enumerate(zip(AGGREGATOR_SITES, scraping_results)):
            if not res:
                self._mark_source(name, "error:scrape_failed")
                continue
            parse_tasks.append(
                self._process_aggregator_payload(
                    res, start_id + idx * stride,
                    origin, destination, depart_date, return_date,
                    fast_parse=False,
                )
            )

        parsed = await gather(*parse_tasks) if parse_tasks else []
        all_options: list[TravelOption] = []
        for opts, _ in parsed:
            all_options.extend(opts)
        return all_options

    async def _process_aggregator_payload(
        self,
        res: dict,
        start_id: int,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
        *,
        fast_parse: bool = False,
    ) -> tuple[list[TravelOption], int]:
        site_name = res["site_name"]
        print(
            f"[ScrapingService]   Aggregator: {site_name}, "
            f"Markdown Length: {len(res['markdown'])}"
        )

        is_blocked, block_reason, block_type = self._classify_blocked_page(
            res["markdown"], res["url"], res.get("page_title", ""), res.get("response_status")
        )
        if is_blocked:
            self._mark_source(site_name, f"blocked:{block_type}:{block_reason}")
            print(f"[ScrapingService]   {site_name} blocked: {block_reason} ({block_type})")
            return [], start_id

        is_valid, valid_reason = self._validate_flight_data(
            res["markdown"], origin, destination, site_name=site_name
        )
        if not is_valid:
            self._mark_source(site_name, f"no_data:{valid_reason}")
            print(f"[ScrapingService]   {site_name} validation failed: {valid_reason}")
            return [], start_id

        print(f"[ScrapingService]   {site_name} validated: {valid_reason}")

        options = await self._parse_with_ai_and_fallback(
            res,
            start_id,
            origin,
            destination,
            depart_date,
            return_date,
            source_type="aggregator",
            fast_parse=fast_parse,
        )

        if not options:
            self._mark_source(site_name, "no_parse")
            print(f"[ScrapingService]   {site_name} returned no parseable flights")
            return [], start_id

        self._mark_source(site_name, "ok")
        out = self._enrich_aggregator_options(
            options,
            res,
            origin,
            destination,
            depart_date,
            return_date,
        )
        return out, start_id + len(out)

    @staticmethod
    def _markdown_has_fare_signals(markdown: str) -> bool:
        if not markdown or len(markdown) < 80:
            return False
        has_price = bool(_PRICE_SIGNAL_RE.search(markdown))
        has_times = bool(
            re.search(r"\d{1,2}:\d{2}\s*[ap]\.?m", markdown, re.IGNORECASE)
        )
        return has_price and has_times

    def _resolve_airline_booking_url(
        self,
        airline_name: str,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
    ) -> str | None:
        """Build a pre-filled booking URL on the carrier site (no scrape required)."""
        if not airline_name:
            return None
        low = airline_name.lower()
        for site_name, template in AIRLINE_SITES:
            site_low = site_name.lower()
            if site_low in low or low in site_low:
                return self._build_airline_url(
                    template, origin, destination, depart_date, return_date
                )
        return None

    def _enrich_aggregator_options(
        self,
        options: list[TravelOption],
        res: dict,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
    ) -> list[TravelOption]:
        """Aggregator row + optional airline row (booking link) per parsed fare."""
        page_src = res.get("page_url") or res["url"]
        flight_links: list[str] = res.get("flight_links") or []
        out: list[TravelOption] = []

        for i, option in enumerate(options):
            link = flight_links[i] if i < len(flight_links) else None
            airline_book_url: str | None = None
            if link and _is_plausible_flight_booking_link(link, page_src):
                airline_book_url = link
            else:
                airline_book_url = self._resolve_airline_booking_url(
                    option.airline, origin, destination, depart_date, return_date
                )

            option.source_type = "aggregator"
            option.source_url = page_src
            out.append(option)

            if airline_book_url:
                out.append(
                    option.model_copy(
                        update={
                            "id": option.id + _AIRLINE_COMPANION_ID_OFFSET,
                            "source_type": "airline",
                            "source_url": airline_book_url,
                        }
                    )
                )
        return out

    async def _process_airline_payload(
        self,
        res: dict,
        start_id: int,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
        *,
        fast_parse: bool = False,
    ) -> tuple[list[TravelOption], int]:
        site_name = res["site_name"]
        is_blocked, block_reason, block_type = self._classify_blocked_page(
            res["markdown"], res["url"], res.get("page_title", ""), res.get("response_status")
        )
        if is_blocked and not self._markdown_has_fare_signals(res["markdown"]):
            self._mark_source(site_name, f"blocked:{block_type}:{block_reason}")
            return [], start_id
        if is_blocked:
            print(
                f"[ScrapingService]   {site_name} challenge detected but fare "
                f"signals present — attempting parse"
            )

        is_valid, valid_reason = self._validate_flight_data(
            res["markdown"], origin, destination, site_name=site_name
        )
        if not is_valid:
            self._mark_source(site_name, f"no_data:{valid_reason}")
            return [], start_id

        options = await self._parse_with_ai_and_fallback(
            res,
            start_id,
            origin,
            destination,
            depart_date,
            return_date,
            source_type="airline",
            fast_parse=fast_parse,
        )
        if not options:
            self._mark_source(site_name, "no_parse")
            return [], start_id

        self._mark_source(site_name, "ok")
        page_src = res.get("page_url") or res["url"]
        booking_url = self._resolve_airline_booking_url(
            site_name, origin, destination, depart_date, return_date
        )
        out: list[TravelOption] = []
        for i, option in enumerate(options):
            if not option.airline or option.airline in _AGGREGATOR_SITE_NAMES:
                option.airline = site_name
            link = (
                res["flight_links"][i]
                if res["flight_links"] and i < len(res["flight_links"])
                else None
            )
            if link and _is_plausible_flight_booking_link(link, page_src):
                option.source_url = link
            else:
                option.source_url = booking_url or page_src
            out.append(option)
        return out, start_id + len(out)

    async def _fetch_airline_raw_timed(
        self,
        site_name: str,
        base_url: str,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
    ) -> dict | None:
        url = self._build_airline_url(
            base_url, origin, destination, depart_date, return_date
        )

        async def _do_scrape():
            try:
                return await self.provider.scrape(url)
            except Exception as e:
                print(f"Airline {site_name} failed: {e}")
                self._mark_source(site_name, f"error:{e}")
                return {"success": False}

        scrape_result = await self._run_timed_scrape(
            site_name, _do_scrape(), _AIRLINE_SCRAPE_TIMEOUT_SEC
        )
        if not scrape_result:
            return None
        if scrape_result.get("success"):
            data = scrape_result.get("data") or {}
            return _build_scrape_payload(
                site_name, url, data, origin=origin, destination=destination
            )
        self._mark_source(site_name, "error:scrape_failed")
        return None

    async def _scrape_airline_sites(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
        start_id: int,
    ) -> List[TravelOption]:
        """Scrape and parse airline websites — all in parallel."""
        print(f"[ScrapingService] Scraping {len(AIRLINE_SITES)} airline site(s)...")

        async def scrape_and_parse(site_name: str, base_url: str, id_start: int) -> list[TravelOption]:
            raw = await self._fetch_airline_raw_timed(
                site_name, base_url, origin, destination, depart_date, return_date
            )
            if not raw:
                return []
            print(
                f"[ScrapingService]   {site_name} scraped {len(raw['markdown'])} chars, "
                f"rows={len(raw.get('flight_row_texts') or [])}"
            )
            try:
                options, _ = await self._process_airline_payload(
                    raw,
                    id_start,
                    origin,
                    destination,
                    depart_date,
                    return_date,
                    fast_parse=False,
                )
            except Exception as e:
                print(f"[ScrapingService]   {site_name} parse error: {e}")
                traceback.print_exc()
                self._mark_source(site_name, f"error:parse:{e}")
                return []
            return options

        stride = 10000
        print(
            f"[ScrapingService] Airline scrape (parallel): "
            f"{', '.join(n for n, _ in AIRLINE_SITES)}"
        )
        batch_results = await gather(
            *[
                scrape_and_parse(name, url, start_id + idx * stride)
                for idx, (name, url) in enumerate(AIRLINE_SITES)
            ]
        )
        all_options: list[TravelOption] = []
        for opts in batch_results:
            all_options.extend(opts)
        return all_options

    async def _parse_with_ai_and_fallback(
        self,
        res: dict,
        start_id: int,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
        source_type: str,
        *,
        fast_parse: bool = False,
    ) -> list[TravelOption]:
        """Parse scraped content: regex first (fast), then AI if needed."""
        markdown = _markdown_with_row_texts(res)
        options = self._parse_flight_from_markdown(
            markdown,
            start_id,
            origin,
            destination,
            res["url"],
            res["site_name"],
            depart_date,
            return_date,
            source_type=source_type,
            canonical_source_url=res.get("page_url") or res["url"],
        )
        if options:
            print(
                f"[ScrapingService] Regex parsed {len(options)} flights from {res['site_name']}"
            )
            return options

        if fast_parse:
            return []

        if not ScrapingService._markdown_has_fare_signals(markdown):
            print(f"[ScrapingService] No fare signals in {res['site_name']}, skipping AI")
            return []

        ai_content = _markdown_for_ai(res, origin, destination)
        print(
            f"[ScrapingService] Regex found no fares for {res['site_name']}; "
            f"AI fallback ({len(ai_content)} chars, was {len(markdown)})"
        )

        try:
            with anyio.fail_after(_AI_TIMEOUT_SEC):
                ai_flights = await self.ai_parser.parse_flights(
                    page_content=ai_content,
                    site_name=res["site_name"],
                    origin=origin,
                    destination=destination,
                    depart_date=depart_date,
                    return_date=return_date,
                )
        except TimeoutError:
            print(f"[ScrapingService] AI parsing timed out for {res['site_name']} after {_AI_TIMEOUT_SEC}s")
            ai_flights = []
        except Exception as e:
            print(f"[ScrapingService] AI parsing failed for {res['site_name']}: {e}")
            ai_flights = []

        if ai_flights:
            options = self.ai_parser.flights_to_options(
                flights=ai_flights,
                start_id=start_id,
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                return_date=return_date,
                source_type=source_type,
                source_url=res.get("page_url") or res["url"],
            )
            if options:
                print(f"[ScrapingService] AI parsed {len(options)} flights from {res['site_name']}")
                return options

        return []

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

    def _build_aggregator_url(
        self,
        template: str,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
    ) -> str:
        """Build aggregator search URL, including return leg when provided."""
        depart_formats = self._parse_date_formats(depart_date)
        url = _apply_aggregator_usd_locale(
            self._format_url(template, origin, destination, depart_formats)
        )
        if not return_date:
            return url

        ret_formats = self._parse_date_formats(return_date)
        low = template.lower()
        o, d = origin.upper(), destination.upper()

        if "google.com" in low:
            ret = (
                f"+return+{ret_formats['month_name']}+"
                f"{ret_formats['day']}+{ret_formats['year']}"
            )
            if "&hl=" in url:
                url = url.replace("&hl=", f"{ret}&hl=", 1)
            elif "&curr=" in url:
                url = url.replace("&curr=", f"{ret}&curr=", 1)
            else:
                url += ret
        elif "kayak.com" in low:
            url = (
                f"https://www.kayak.com/flights/{o}-{d}/"
                f"{depart_formats['year']}-{depart_formats['month']}-{depart_formats['day']}/"
                f"{ret_formats['year']}-{ret_formats['month']}-{ret_formats['day']}"
                f"?sort=price_a&currency=USD"
            )
        elif "skyscanner.com" in low:
            url = (
                f"https://www.skyscanner.com/transport/flights/{o}/{d}/"
                f"{depart_formats['year']}-{depart_formats['month']}-{depart_formats['day']}/"
                f"{ret_formats['year']}-{ret_formats['month']}-{ret_formats['day']}/"
                f"?currency=USD&market=US&locale=en-US"
            )
        elif "expedia.com" in low:
            url = (
                f"https://www.expedia.com/Flights-Search?trip=roundtrip"
                f"&leg1=from%3A{o}%2Cto%3A{d}%2Cdeparture%3A"
                f"{depart_formats['year']}-{depart_formats['month']}-{depart_formats['day']}TANYT"
                f"&leg2=from%3A{d}%2Cto%3A{o}%2Cdeparture%3A"
                f"{ret_formats['year']}-{ret_formats['month']}-{ret_formats['day']}TANYT"
                f"&passengers=adults%3A1%2Cseniors%3A0%2Cchildren%3A0%2Cinfants%3A0"
                f"&mode=search&locale=en_US&currency=USD"
            )

        return _apply_aggregator_usd_locale(url)

    def _build_airline_url(
        self,
        template: str,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None,
    ) -> str:
        """Build direct airline booking URL matching each carrier’s query-string format."""
        o, d = origin.upper(), destination.upper()
        dep = self._parse_date_formats(depart_date)
        dep_iso = dep.get("date_iso", depart_date)
        ret_iso = (
            self._parse_date_formats(return_date).get("date_iso", return_date)
            if return_date
            else None
        )
        low = template.lower()

        if "copaair.com" in low:
            url = (
                f"https://www.copaair.com/en-us/flights?"
                f"origin={o}&destination={d}&departDate={dep_iso}&passengers=1"
            )
            if ret_iso:
                url += f"&returnDate={ret_iso}"
            return url

        if "aeromexico.com" in low:
            url = (
                f"https://www.aeromexico.com/en-us/flights?"
                f"origin={o}&destination={d}&departDate={dep_iso}&passengers=1"
            )
            if ret_iso:
                url += f"&returnDate={ret_iso}"
            return url

        if "avianca.com" in low:
            url = (
                f"https://www.avianca.com/en/booking/select/?"
                f"origin1={o}&destination1={d}&departure1={dep_iso}&adt1=1&currency=USD"
            )
            if ret_iso:
                url += f"&return1={ret_iso}"
            return url

        if "delta.com" in low:
            trip = "ROUND_TRIP" if ret_iso else "ONE_WAY"
            url = (
                f"https://www.delta.com/flight-search/book-a-flight?"
                f"departureDate={dep_iso}&destinationAirportCode={d}"
                f"&originAirportCode={o}&tripType={trip}&paxCount=1"
            )
            if ret_iso:
                url += f"&returnDate={ret_iso}"
            return url

        if "united.com" in low:
            trip_path = "rt" if ret_iso else "ow"
            url = (
                f"https://www.united.com/en/us/fsr/{trip_path}/search?"
                f"origin={o}&destination={d}&departDate={dep_iso}&passengers=1"
            )
            if ret_iso:
                url += f"&returnDate={ret_iso}"
            return url

        if "aa.com" in low:
            url = (
                f"https://www.aa.com/booking/find-flights?"
                f"origin={o}&destination={d}&departDate={dep_iso}&passengers=1"
            )
            if ret_iso:
                url += f"&returnDate={ret_iso}"
            return url

        if "southwest.com" in low:
            url = (
                f"https://www.southwest.com/air/booking/select.html?"
                f"originationAirportCode={o}&destinationAirportCode={d}"
                f"&outboundDate={dep_iso}&adultPassengersCount=1"
            )
            if ret_iso:
                url += f"&returnDate={ret_iso}"
            return url

        return self._format_url(template, origin, destination, dep)

    def _get_booking_url(
        self,
        site_name: str,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None = None,
    ) -> str:
        """Generate direct booking URL with proper parameters for each airline."""
        origin_code = origin.upper()
        dest_code = destination.upper()

        is_roundtrip = return_date is not None

        google_flights = _apply_aggregator_usd_locale(
            f"https://www.google.com/travel/flights?q=flights+from+{origin_code}+to+{dest_code}"
            f"+on+{depart_date}"
            + (f"+return+{return_date}" if is_roundtrip else "")
        )
        kayak_url = (
            f"https://www.kayak.com/flights/{origin_code}-{dest_code}/"
            f"{depart_date}/{return_date}?sort=price_a&currency=USD"
            if is_roundtrip
            else f"https://www.kayak.com/flights/{origin_code}-{dest_code}/"
            f"{depart_date}?sort=price_a&currency=USD"
        )
        skyscanner_url = (
            f"https://www.skyscanner.com/transport/flights/{origin_code}/{dest_code}/"
            f"{depart_date}/{return_date}/?currency=USD&market=US&locale=en-US"
            if is_roundtrip
            else f"https://www.skyscanner.com/transport/flights/{origin_code}/{dest_code}/"
            f"{depart_date}/?currency=USD&market=US&locale=en-US"
        )
        expedia_url = (
            f"https://www.expedia.com/Flights-Search?trip=roundtrip"
            f"&leg1=from%3A{origin_code}%2Cto%3A{dest_code}%2Cdeparture%3A{depart_date}TANYT"
            f"&leg2=from%3A{dest_code}%2Cto%3A{origin_code}%2Cdeparture%3A{return_date}TANYT"
            f"&passengers=adults%3A1%2Cseniors%3A0%2Cchildren%3A0%2Cinfants%3A0"
            f"&mode=search&locale=en_US&currency=USD"
            if is_roundtrip
            else f"https://www.expedia.com/Flights-Search?flight-type=on&starDate={depart_date}"
            f"&endDate=&trip=oneway&leg1=from%3A{origin_code}%2Cto%3A{dest_code}%2Cdeparture%3A"
            f"{depart_date}TANYT&passengers=adults%3A1%2Cseniors%3A0%2Cchildren%3A0%2Cinfants%3A0"
            f"&mode=search&locale=en_US&currency=USD"
        )

        booking_urls = {
            "google": google_flights,
            "kayak": _apply_aggregator_usd_locale(kayak_url),
            "skyscanner": _apply_aggregator_usd_locale(skyscanner_url),
            "expedia": _apply_aggregator_usd_locale(expedia_url),
        }

        site_key = site_name.lower()
        if site_key in booking_urls:
            return booking_urls[site_key]

        direct = self._resolve_airline_booking_url(
            site_name, origin_code, dest_code, depart_date, return_date
        )
        if direct:
            return direct

        return google_flights

    def _build_line_flight_blocks(
        self, markdown: str, origin: str, destination: str
    ) -> list[str]:
        """Group markdown lines that look like a single fare row."""
        flight_blocks: list[str] = []
        lines = markdown.split("\n")
        current_block: list[str] = []
        origin_u, dest_u = origin.upper(), destination.upper()
        for line in lines:
            line = line.strip()
            if not line:
                if current_block:
                    flight_blocks.append(" ".join(current_block))
                    current_block = []
                continue
            if any(
                x in line.lower()
                for x in [
                    "$",
                    "am",
                    "pm",
                    "stop",
                    "hour",
                    "flight",
                    origin_u,
                    dest_u,
                ]
            ):
                current_block.append(line)
            elif current_block:
                flight_blocks.append(" ".join(current_block))
                current_block = []
        if current_block:
            flight_blocks.append(" ".join(current_block))
        return [b for b in flight_blocks if len(b) >= 30]

    def _parse_flight_blocks_from_list(
        self,
        flight_blocks: list[str],
        start_id: int,
        origin: str,
        destination: str,
        site_name: str,
        depart_date: str,
        return_date: str | None,
        source_type: str,
        canonical_source_url: str | None,
    ) -> List[TravelOption]:
        """Parse a list of row/snippet strings (Playwright rows, offer windows, etc.)."""
        options: List[TravelOption] = []
        parsed_count = 0

        for block_idx, block in enumerate(flight_blocks):
            if len(block) < 20:
                continue

            block_lower = block.lower()

            if source_type == "aggregator" and not _route_codes_in_text(
                block, origin, destination
            ):
                continue

            price_match = _USD_PRICE_CAPTURE_RE.search(block)
            if not price_match:
                offer_match = _AGGREGATOR_OFFER_PRICE_RE.search(block)
                if not offer_match:
                    continue
                price = float(offer_match.group(1).replace(",", ""))
                price_match = offer_match
            else:
                price = float(price_match.group(1).replace(",", ""))

            if price < _MIN_FARE_USD or price > _MAX_FARE_USD:
                continue

            tail = block[price_match.start() :]
            time_matches = re.findall(
                r"(\d{1,2}:\d{2}\s*[AP]\.?M\.?)", tail, re.IGNORECASE
            )
            if len(time_matches) < 2:
                time_matches = re.findall(
                    r"(\d{1,2}\s*[AP]\.?M\.?)", tail, re.IGNORECASE
                )

            depart_time = "08:00 AM"
            arrival_time = "11:00 AM"
            if len(time_matches) >= 2:
                depart_time = (
                    time_matches[0].strip().upper().replace(".", "").replace(" ", "")
                )
                arrival_time = (
                    time_matches[1].strip().upper().replace(".", "").replace(" ", "")
                )
            elif len(time_matches) == 1:
                depart_time = (
                    time_matches[0].strip().upper().replace(".", "").replace(" ", "")
                )

            depart_time = _normalize_time_12h(depart_time) or depart_time
            arrival_time = _normalize_time_12h(arrival_time) or arrival_time

            stops = self._parse_stops_from_text(block_lower)

            duration = "2h 30m"
            duration_match = re.search(
                r"(\d+)h\s*m|(\d+)h(\d+)m|(\d+)\s*hour", block_lower
            )
            if duration_match:
                if duration_match.group(1):
                    duration = f"{duration_match.group(1)}h"
                elif duration_match.group(2) and duration_match.group(3):
                    duration = f"{duration_match.group(2)}h {duration_match.group(3)}m"

            airline_name = _finalize_carrier_name(
                _carrier_from_itinerary_snippet(
                    block, site_name, origin, destination
                ),
                site_name,
                source_type,
            )
            if not airline_name:
                continue

            print(
                f"[Parser]   Block {block_idx}: ${price}, {depart_time}->{arrival_time}, "
                f"{airline_name}, stops={stops}"
            )

            booking_url = self._get_booking_url(
                airline_name.lower(),
                origin,
                destination,
                str(depart_date),
                str(return_date) if return_date else None,
            )
            source_url = canonical_source_url or booking_url

            options.append(
                TravelOption(
                    id=start_id + parsed_count,
                    airline=airline_name,
                    price=price,
                    depart_time=depart_time,
                    arrival_time=arrival_time,
                    duration=duration,
                    stops=stops,
                    source_url=source_url,
                    source_type=source_type,
                    depart_date=str(depart_date) if depart_date else None,
                    return_date=str(return_date) if return_date else None,
                )
            )
            parsed_count += 1
            if parsed_count >= _MAX_FLIGHTS_PER_SCRAPE:
                break

        return options

    def _parse_aggregator_offer_cards(
        self,
        markdown: str,
        start_id: int,
        origin: str,
        destination: str,
        site_name: str,
        depart_date: str,
        return_date: str | None,
        source_type: str,
        canonical_source_url: str | None,
    ) -> List[TravelOption]:
        """Kayak/Copa-style 'From USD 677' snippets without a leading $."""
        snippets: list[str] = []
        seen: set[int] = set()
        for match in _AGGREGATOR_OFFER_PRICE_RE.finditer(markdown):
            pos = match.start()
            bucket = pos // 200
            if bucket in seen:
                continue
            seen.add(bucket)
            start = max(0, pos - 500)
            end = min(len(markdown), match.end() + 350)
            snippet = markdown[start:end].strip()
            if len(snippet) < 25:
                continue
            if source_type == "aggregator" and not _route_codes_in_text(
                snippet, origin, destination
            ):
                continue
            snippets.append(snippet)
            if len(snippets) >= _MAX_FLIGHTS_PER_SCRAPE:
                break

        if not snippets:
            return []
        return self._parse_flight_blocks_from_list(
            snippets,
            start_id,
            origin,
            destination,
            site_name,
            depart_date,
            return_date,
            source_type,
            canonical_source_url,
        )

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
        source_type: str = "direct",
        canonical_source_url: str | None = None,
    ) -> List[TravelOption]:
        """Regex-first parse: row blocks, Google, offer cards, price scan, then line blocks."""
        print(f"[Parser] Processing {site_name}, content length: {len(markdown)}")
        print(f"[Parser] Looking for origin={origin}, dest={destination}")

        has_origin_code = re.search(rf"\b{origin.upper()}\b", markdown)
        has_destination_code = re.search(rf"\b{destination.upper()}\b", markdown)

        if not (has_origin_code and has_destination_code):
            if source_type in ("direct", "airline"):
                print(
                    f"[Parser] Airport codes not in page text; continuing for airline {site_name}"
                )
            else:
                print("[Parser] Origin or destination code not found in content, rejecting")
                return []

        common = (
            start_id,
            origin,
            destination,
            site_name,
            depart_date,
            return_date,
            source_type,
            canonical_source_url,
        )

        row_blocks = [
            b.strip() for b in _ROW_BLOCK_RE.findall(markdown) if len(b.strip()) >= 20
        ]
        if row_blocks:
            print(f"[Parser] Trying {len(row_blocks)} Playwright row blocks first")
            opts = self._parse_flight_blocks_from_list(row_blocks, *common)
            if opts:
                print(f"[Parser] Row blocks extracted {len(opts)} flights")
                return opts

        if "google" in site_name.lower():
            google_opts = self._parse_google_flights_itineraries(
                markdown, *common
            )
            if google_opts:
                print(f"[Parser] Google scan extracted {len(google_opts)} flights")
                return google_opts

        offer_opts = self._parse_aggregator_offer_cards(markdown, *common)
        if offer_opts:
            print(f"[Parser] Offer-card scan extracted {len(offer_opts)} flights")
            return offer_opts

        scanned = self._parse_fares_by_price_scan(markdown, *common)
        if scanned:
            print(f"[Parser] Price-scan extracted {len(scanned)} flights from {site_name}")
            return scanned

        line_blocks = self._build_line_flight_blocks(markdown, origin, destination)
        print(f"[Parser] Fallback: {len(line_blocks)} line-grouped blocks")
        return self._parse_flight_blocks_from_list(line_blocks, *common)

    @staticmethod
    def _parse_stops_from_text(text_lower: str) -> int:
        """Infer stop count from a single itinerary snippet (not the whole page)."""
        if re.search(
            r"\bnon-?stop\b|\bdirect\b|\b0\s*stops?\b|\bno\s*stops?\b",
            text_lower,
        ):
            return 0
        if re.search(r"\b1\s*stop\b|\+\s*1\s*stop\b|\bone\s*stop\b", text_lower):
            return 1
        if re.search(r"\b2\s*stops?\b|\+\s*2\s*stops?\b", text_lower):
            return 2
        if re.search(r"\b3\s*stops?\b", text_lower):
            return 3
        stop_match = re.search(r"(\d+)\s*stops?\b", text_lower)
        if stop_match:
            return int(stop_match.group(1))
        if re.search(r"\blayover\b|\bconnecting\b", text_lower):
            return 1
        return 0

    def _parse_google_flights_itineraries(
        self,
        markdown: str,
        start_id: int,
        origin: str,
        destination: str,
        site_name: str,
        depart_date: str,
        return_date: str | None,
        source_type: str,
        canonical_source_url: str | None,
    ) -> List[TravelOption]:
        """Match Google result cards: itinerary text then ``$price`` + ``round trip``."""
        options: List[TravelOption] = []
        seen: set[tuple] = set()
        is_roundtrip = bool(return_date)

        patterns: list[re.Pattern[str]] = []
        if is_roundtrip:
            patterns.append(_GOOGLE_ROUNDTRIP_PRICE_RE)
        else:
            patterns.append(_GOOGLE_ONEWAY_PRICE_RE)
            patterns.append(_GOOGLE_ROUNDTRIP_PRICE_RE)

        for pattern in patterns:
            for match in pattern.finditer(markdown):
                raw = match.group(1).replace(",", "")
                try:
                    price = float(raw)
                except ValueError:
                    continue
                if price < _MIN_FARE_USD or price > _MAX_FARE_USD:
                    continue

                win_start = max(0, match.start() - 700)
                window = markdown[win_start : match.start()]

                if not _route_codes_in_text(window, origin, destination):
                    continue

                window_lower = window.lower()

                time_matches = re.findall(
                    r"(\d{1,2}:\d{2}\s*[AP]\.?M\.?)", window, re.IGNORECASE
                )
                if len(time_matches) < 2:
                    continue
                depart_time = _normalize_time_12h(time_matches[-2]) or time_matches[-2]
                arrival_time = _normalize_time_12h(time_matches[-1]) or time_matches[-1]

                key = (round(price, 2), depart_time, arrival_time)
                if key in seen:
                    continue
                seen.add(key)

                stops = self._parse_stops_from_text(window_lower)
                duration = ""
                dur_m = re.search(r"(\d+)\s*hr\s*(\d+)?\s*min", window_lower)
                if dur_m:
                    duration = (
                        f"{dur_m.group(1)}h {dur_m.group(2)}m"
                        if dur_m.group(2)
                        else f"{dur_m.group(1)}h"
                    )

                airline_name = _finalize_carrier_name(
                    _carrier_from_itinerary_snippet(
                        window, site_name, origin, destination
                    ),
                    site_name,
                    source_type,
                )
                if not airline_name:
                    continue

                options.append(
                    TravelOption(
                        id=start_id + len(options),
                        airline=airline_name,
                        price=round(price, 2),
                        depart_time=depart_time,
                        arrival_time=arrival_time,
                        duration=duration,
                        stops=stops,
                        source_url=canonical_source_url or "",
                        source_type=source_type,
                        depart_date=str(depart_date) if depart_date else None,
                        return_date=str(return_date) if return_date else None,
                    )
                )
                if len(options) >= _MAX_FLIGHTS_PER_SCRAPE:
                    return options

        return options

    def _parse_fares_by_price_scan(
        self,
        markdown: str,
        start_id: int,
        origin: str,
        destination: str,
        site_name: str,
        depart_date: str,
        return_date: str | None,
        source_type: str,
        canonical_source_url: str | None,
    ) -> List[TravelOption]:
        """Extract fares by scanning for $price windows (works on dense aggregator pages)."""
        options: List[TravelOption] = []
        seen_prices: set[tuple] = set()

        price_pattern = re.compile(
            r"(?:US\$|\$|USD)\s*([\d,]+(?:\.\d{2})?)|"
            r"from\s+(?:US\$|\$|USD)\s*([\d,]+)",
            re.IGNORECASE,
        )
        for match in price_pattern.finditer(markdown):
            raw = (match.group(1) or match.group(2) or "").replace(",", "")
            try:
                price_val = float(raw)
            except ValueError:
                continue
            if price_val < _MIN_FARE_USD or price_val > _MAX_FARE_USD:
                continue
            after = markdown[match.end() : match.end() + 80].lower()
            if return_date and "google" in site_name.lower():
                if "round trip" not in after and "round-trip" not in after:
                    continue
            price = int(price_val) if price_val == int(price_val) else round(price_val, 2)
            # Fare text follows the itinerary on Google Flights — read mostly backward
            win_start = max(0, match.start() - 550)
            window = markdown[win_start : match.start() + 120]

            if source_type == "aggregator" and not _route_codes_in_text(
                window, origin, destination
            ):
                continue

            time_matches = re.findall(
                r"(\d{1,2}:\d{2}\s*[AP]\.?M\.?)", window, re.IGNORECASE
            )
            if len(time_matches) < 2:
                continue
            depart_time = _normalize_time_12h(time_matches[-2]) or time_matches[-2]
            arrival_time = _normalize_time_12h(time_matches[-1]) or time_matches[-1]
            key = (price, depart_time, arrival_time)
            if key in seen_prices:
                continue
            seen_prices.add(key)

            window_lower = window.lower()
            stops = self._parse_stops_from_text(window_lower)

            duration = ""
            dur_m = re.search(
                r"(\d+)\s*hr\s*(\d+)?\s*min", window_lower
            )
            if dur_m:
                duration = (
                    f"{dur_m.group(1)}h {dur_m.group(2)}m"
                    if dur_m.group(2)
                    else f"{dur_m.group(1)}h"
                )

            airline_name = _finalize_carrier_name(
                _carrier_from_itinerary_snippet(
                    window, site_name, origin, destination
                ),
                site_name,
                source_type,
            )
            if not airline_name:
                continue

            options.append(
                TravelOption(
                    id=start_id + len(options),
                    airline=airline_name,
                    price=float(price),
                    depart_time=depart_time,
                    arrival_time=arrival_time,
                    duration=duration,
                    stops=stops,
                    source_url=canonical_source_url or "",
                    source_type=source_type,
                    depart_date=str(depart_date) if depart_date else None,
                    return_date=str(return_date) if return_date else None,
                )
            )
            if len(options) >= _MAX_FLIGHTS_PER_SCRAPE:
                break

        return options

    def _classify_blocked_page(
        self,
        markdown: str,
        url: str,
        page_title: str = "",
        http_status: int | None = None,
    ) -> tuple[bool, str, str]:
        """Detect if page is blocked.

        Returns (is_blocked, readable_reason, block_category).
        block_category is one of: captcha, waf_js, rate_limit, permission,
        blocked_country, empty, generic, ""
        """
        content_lower = markdown.lower()
        title_lower = page_title.lower()
        url_lower = url.lower()

        # HTTP status check (most reliable signal)
        if http_status is not None:
            if http_status == 429:
                return True, "Rate limited (HTTP 429)", "rate_limit"
            if http_status == 403:
                return True, "Access forbidden (HTTP 403)", "permission"
            if http_status == 451:
                return True, "Blocked by legal restriction (HTTP 451)", "blocked_country"
            if http_status == 503 and "cloudflare" in content_lower[:1000]:
                return True, "Cloudflare WAF challenge (HTTP 503)", "waf_js"
            if http_status >= 400:
                return True, f"HTTP {http_status} error", "generic"

        # URL-based challenge detection: Cloudflare redirects to challenge URLs
        challenge_url_patterns = [
            "__cf_chl_rt", "__cf_chl_ctx", "__cf_chl_tk",
            "cdn-cgi/challenge-platform", "cloudflare.com/cdn-cgi/",
            "_cf_dns", "cf-ray", "ray id",
            "/.well-known/cf-challenge", "cloudflare/gateway",
            "challenges.cloudflare.com",
        ]
        for pattern in challenge_url_patterns:
            if pattern in url_lower:
                return True, "Challenge URL detected", "waf_js"

        # Page title patterns
        title_block_signals = {
            "just a moment": ("Cloudflare JS challenge", "waf_js"),
            "attention required": ("Cloudflare CAPTCHA", "captcha"),
            "please verify": ("Verification required", "captcha"),
            "access denied": ("Access denied", "permission"),
            "forbidden": ("Forbidden", "permission"),
            "blocked": ("Blocked", "generic"),
            "sorry": ("Blocked", "generic"),
            "pardon our interruption": ("Akamai WAF", "waf_js"),
            "automated access": ("Blocked", "permission"),
            "403 forbidden": ("Forbidden", "permission"),
            "connection denied": ("Connection denied", "generic"),
        }
        for pattern, (reason, category) in title_block_signals.items():
            if pattern in title_lower:
                return True, reason, category

        # Content slice for lightweight pattern matching
        first_1k = content_lower[:1000]

        # Content-based block patterns — weighted scoring
        score = 0
        reasons = []

        captcha_patterns = [
            "captcha", "recaptcha", "hcaptcha", "turnstile",
            "cf-turnstile", "g-recaptcha", "data-sitekey",
            "please verify you are human", "verify your identity",
            "are you a human", "prove you are human",
            "security check", "verification required",
            "enter the characters", "type the characters",
            "image verification", "visual verification",
        ]
        for p in captcha_patterns:
            if p in first_1k:
                score += 3
                reasons.append("captcha")
                break

        waf_patterns = [
            "checking your browser", "checking the browser",
            "your browser will be redirected", "you are being redirected",
            "cloudflare", "cloudflare-nginx",
            "attention: requires verification",
            "reference #", "ray id:", "cf-ray",
            "challenge-platform", "monitor and secure",
            "perimeterx", "px-block", "px-blocked",
            "datadome", "data-dome", "botmanager",
            "akamai", "akamaiedge",
            "incapsula", "block reason",
        ]
        for p in waf_patterns:
            if p in content_lower:
                score += 2
                reasons.append("waf")
                break

        rate_limit_patterns = [
            "too many requests", "rate limit", "rate limited",
            "error 429", "429 too many",
            "try again later", "please try again later",
            "slow down", "temporarily blocked",
        ]
        for p in rate_limit_patterns:
            if p in first_1k:
                score += 3
                reasons.append("rate_limit")
                break

        permission_patterns = [
            "access denied", "access forbidden",
            "error 403", "403 forbidden",
            "permission denied", "not authorized",
            "you do not have permission", "access prohibited",
            "blocked", "your ip has been blocked",
            "your access has been blocked", "suspended",
            "unusual traffic", "automated access",
        ]
        for p in permission_patterns:
            if p in first_1k:
                score += 2
                reasons.append("permission")
                break

        js_required_patterns = [
            "enable javascript", "javascript is disabled",
            "turn on javascript", "javascript required",
            "please enable javascript", "enable cookies",
            "cookies are disabled", "we need javascript",
            "your browser does not support javascript",
        ]
        for p in js_required_patterns:
            if p in first_1k:
                score += 1
                reasons.append("waf_js")
                break

        # Generic catch-all patterns (low weight)
        generic_block_patterns = [
            "access to this resource", "access to this site",
            "has been blocked", "resource you are looking for has been blocked",
            "sorry, something went wrong", "something went wrong",
            "we are sorry", "this site is not available",
            "temporarily unavailable", "service unavailable",
            "website is offline", "under maintenance",
        ]
        for p in generic_block_patterns:
            if p in content_lower:
                score += 1
                reasons.append("generic")
                break

        # Content length check
        stripped_len = len(markdown.strip())
        if stripped_len < 200:
            score += 4
            reasons.append("empty")
        elif stripped_len < 400:
            score += 2
            reasons.append("empty")

        if score >= 3 and reasons:
            primary = reasons[0]
            readable = {
                "captcha": "CAPTCHA/verification challenge",
                "waf": "WAF/bot protection challenge",
                "waf_js": "JavaScript challenge page",
                "rate_limit": "Rate limited",
                "permission": "Access denied",
                "empty": "Content too short",
                "generic": "Blocked by site protection",
            }.get(primary, "Blocked")
            return True, readable, primary

        return False, "", ""

    def _validate_flight_data(
        self,
        markdown: str,
        origin: str,
        destination: str,
        *,
        site_name: str = "",
    ) -> tuple[bool, str]:
        """Validate that content contains real flight data for the specific route."""
        origin_u = re.escape(origin.upper())
        dest_u = re.escape(destination.upper())
        has_origin_code = bool(re.search(rf"\b{origin_u}\b", markdown, re.IGNORECASE))
        has_dest_code = bool(re.search(rf"\b{dest_u}\b", markdown, re.IGNORECASE))
        has_codes = has_origin_code and has_dest_code

        has_price = bool(_PRICE_SIGNAL_RE.search(markdown))
        has_times = bool(
            re.search(r"\d{1,2}:\d{2}\s*[ap]\.?m", markdown, re.IGNORECASE)
        )

        flight_indicators = 0
        for pattern in [
            r"\$ ?[0-9]+",
            r"(hour|hr|h)",
            r"(flight|trip|route)",
            r"(depart|arriv|departure|arrival)",
            r"(airline|airport|nonstop|layover)",
        ]:
            if re.search(pattern, markdown, re.IGNORECASE):
                flight_indicators += 1

        is_airline_site = site_name in _AIRLINE_SITE_NAMES
        if is_airline_site:
            if has_price and (has_times or flight_indicators >= 1):
                return True, "Airline page with fares"
            if len(markdown) > 800 and (has_price or has_times or flight_indicators >= 2):
                return True, "Airline booking page content"
            if len(markdown) > 2500:
                return True, "Airline page (large content)"
            return False, "No airline fares detected"

        if has_codes and flight_indicators >= 2:
            return True, "Valid flight data (route codes)"
        if has_codes and has_price:
            return True, "Route codes and price"
        if has_price and (has_times or flight_indicators >= 2):
            return True, "Price and schedule signals"
        if len(markdown) > 1500 and has_price and flight_indicators >= 1:
            return True, "Rich page with pricing"

        if not has_codes:
            return False, "Origin/destination codes not found"
        return False, "No flight data"

    def _make_search_fallbacks(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None = None,
        reason: str = "",
    ) -> List[TravelOption]:
        """Deep links to aggregators when scraping/parsing did not return fares."""
        date_formats = self._parse_date_formats(depart_date)
        options: List[TravelOption] = []
        for i, (site_name, template) in enumerate(AGGREGATOR_SITES[:4]):
            url = self._format_url(template, origin, destination, date_formats)
            label = f"Search on {site_name}"
            if reason == "timeout":
                label = f"{label} (search timed out — open to view fares)"
            options.append(
                TravelOption(
                    id=i,
                    airline=label,
                    price=0,
                    depart_time="",
                    arrival_time="",
                    duration="",
                    stops=0,
                    source_url=url,
                    source_type="search",
                    depart_date=str(depart_date) if depart_date else None,
                    return_date=str(return_date) if return_date else None,
                )
            )

        if options:
            print(f"[ScrapingService] Returning {len(options)} search fallback link(s) ({reason})")
        return options

    def _make_google_flights_fallback(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str | None = None,
    ) -> TravelOption | None:
        """Generate a Google Flights link when all direct scraping fails."""
        origin_code = origin.upper()
        dest_code = destination.upper()

        is_roundtrip = return_date is not None
        url = _apply_aggregator_usd_locale(
            f"https://www.google.com/travel/flights?q=flights+from+{origin_code}"
            f"+to+{dest_code}+on+{depart_date}"
            + (f"+return+{return_date}" if is_roundtrip else "")
        )

        label = "Google Flights" if not is_roundtrip else "Google Flights (round trip)"

        return TravelOption(
            id=0,
            airline=label,
            price=0,
            depart_time="",
            arrival_time="",
            duration="",
            stops=0,
            source_url=url,
            source_type="search",
            depart_date=str(depart_date) if depart_date else None,
            return_date=str(return_date) if return_date else None,
        )