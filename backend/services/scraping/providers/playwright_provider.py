import os
import random
import re
import sys
from typing import TYPE_CHECKING, List, Dict, Any, Optional
from urllib.parse import urlsplit, urlunsplit

import anyio
from concurrency import gather

if TYPE_CHECKING:
    from playwright.async_api import Geolocation, ViewportSize

from .base import ScrapingProvider

_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() not in ("false", "0", "no")
_FAST_MODE = os.getenv("PLAYWRIGHT_FAST_MODE", "true").lower() not in ("false", "0", "no")
_NAV_TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_NAV_TIMEOUT_MS", "15000"))
_MAX_CONCURRENT_PAGES = max(1, int(os.getenv("PLAYWRIGHT_MAX_CONCURRENT", "3")))
_PAGE_TOTAL_TIMEOUT_SEC = float(os.getenv("PLAYWRIGHT_PAGE_TIMEOUT_SEC", "60"))
_BROWSER_LAUNCH_TIMEOUT_SEC = float(os.getenv("PLAYWRIGHT_BROWSER_LAUNCH_TIMEOUT", "30"))
_page_semaphore = anyio.Semaphore(_MAX_CONCURRENT_PAGES)

# ── Anti-detection: browser launch args ──────────────────────────
_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-gpu",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-features=BlockInsecurePrivateNetworkRequests",
    "--disable-infobars",
    "--disable-notifications",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-breakpad",
    "--disable-component-extensions-with-background-pages",
    "--disable-extensions",
    "--disable-features=TranslateUI",
    "--disable-ipc-flooding-protection",
    "--disable-renderer-backgrounding",
    "--enable-features=NetworkService,NetworkServiceInProcess",
    "--force-color-profile=srgb",
    "--hide-scrollbars",
    "--metrics-recording-only",
    "--mute-audio",
    "--no-first-run",
    "--password-store=basic",
    "--use-gl=swiftshader",
]

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

_VIEWPORTS: List["ViewportSize"] = [
    {"width": 1280, "height": 720},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1920, "height": 1080},
    {"width": 1280, "height": 800},
]

_DEFAULT_GEOLOCATION: "Geolocation" = {"latitude": 40.7128, "longitude": -74.0060}

# Host-specific selectors (airline booking UIs differ from aggregators)
_AIRLINE_HOST_HINTS: dict[str, list[str]] = {
    "delta.com": [
        '[class*="flight-result"]', '[class*="FlightResult"]',
        '[data-testid*="flight"]', '[class*="price"]',
        '[class*="itinerary"]', 'button[class*="fare"]',
    ],
    "united.com": [
        '[class*="ResultCard"]', '[class*="flight-result"]',
        '[class*="price"]', '[data-testid*="flight"]',
        '[class*="itin"]', 'article',
    ],
    "aa.com": [
        '[class*="flight-card"]', '[class*="FlightCard"]',
        '[class*="result"]', '[class*="price"]',
        '[data-testid*="flight"]', 'table tbody tr',
    ],
    "southwest.com": [
        '[class*="price"]', '[data-qa*="price"]',
        '[class*="flight"]', '[class*="fare"]',
        '[class*="itinerary"]', 'li[role="listitem"]',
    ],
    "avianca.com": [
        '[class*="flight"]', '[class*="fare"]',
        '[class*="price"]', '[class*="result"]',
    ],
    "copaair.com": [
        '[class*="flight"]', '[class*="fare"]',
        '[class*="price"]', '[class*="result"]',
    ],
    "aeromexico.com": [
        '[class*="flight"]', '[class*="fare"]',
        '[class*="price"]', '[class*="result"]',
    ],
}

_AGGREGATOR_HOST_HINTS: dict[str, list[str]] = {
    "google.com": [
        '[role="listitem"]', '[class*="pIav2d"]',
        '[data-testid*="flight"]', '[class*="price"]',
    ],
    "kayak.com": [
        '[class*="result"]', '[class*="Base-Results"]',
        '[class*="price"]', 'div[role="button"]',
    ],
    "skyscanner.com": [
        '[class*="FlightsTicket"]', '[class*="Price"]',
        '[data-testid*="ticket"]', 'li[role="listitem"]',
    ],
    "expedia.com": [
        '[data-stid*="offer"]', '[class*="uitk-card"]',
        '[class*="price"]', '[class*="flight"]',
    ],
}

# ── Stealth init script ──────────────────────────────────────────
_STEALTH_INIT_SCRIPT = """
// ── Hide webdriver ──
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// ── Fake plugins ──
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5].map(() => ({
        name: 'Chrome PDF Plugin',
        filename: 'internal-pdf-viewer',
        description: 'Portable Document Format'
    }))
});

// ── Languages ──
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

// ── Hardware concurrency (realistic) ──
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

// ── Chrome runtime ──
window.chrome = {
    runtime: { connect: () => {}, sendMessage: () => {} },
    loadTimes: function() { return {} },
    csi: function() { return {} },
    app: { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } },
    webstore: 'WebStore',
};

// ── WebGL vendor (realistic Intel GPU) ──
(() => {
    const proto = WebGLRenderingContext.prototype;
    const origGetParameter = proto.getParameter;
    proto.getParameter = function(p) {
        if (p === 37445) return 'Intel Inc.';
        if (p === 37446) return 'Intel Iris OpenGL Engine';
        return origGetParameter.call(this, p);
    };
})();

// ── Permissions: suppress notification popup ──
const origQuery = window.navigator.permissions.query.bind(window.navigator.permissions);
window.navigator.permissions.query = (params) => {
    if (params && (params.name === 'notifications' || params.name === 'clipboard-write')) {
        return Promise.resolve({ state: 'prompt', onchange: null });
    }
    return origQuery(params);
};

// ── Screen dimensions: match viewport ──
Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
Object.defineProperty(screen, 'orientation', { get: () => ({ type: 'landscape-primary', angle: 0 }) });

// ── Media devices: fake a real camera / mic list ──
if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
    const origEnumerate = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
    navigator.mediaDevices.enumerateDevices = () =>
        origEnumerate().catch(() =>
            Promise.resolve([
                { deviceId: 'audioinput-1', kind: 'audioinput', label: 'Internal Microphone', groupId: 'group1' },
                { deviceId: 'videoinput-1', kind: 'videoinput', label: 'FaceTime HD Camera', groupId: 'group2' },
                { deviceId: 'audiooutput-1', kind: 'audiooutput', label: 'Internal Speakers', groupId: 'group3' },
            ])
        );
}

// ── Connection (realistic values) ──
if (navigator.connection) {
    Object.defineProperty(navigator.connection, 'effectiveType', { get: () => '4g' });
    Object.defineProperty(navigator.connection, 'rtt', { get: () => 50 });
    Object.defineProperty(navigator.connection, 'downlink', { get: () => 10 });
    Object.defineProperty(navigator.connection, 'saveData', { get: () => false });
}
"""

# ── Flight row extractors ────────────────────────────────────────
_FLIGHT_ROW_EXTRACTOR = """
() => {
    const priceRe = /(?:\\$|USD|US\\$)\\s*[\\d,]+|\\d{1,4}\\s*(?:USD|usd)/i;
    const timeRe = /\\d{1,2}:\\d{2}\\s*[AP]\\.?M\\.?|\\d{1,2}\\s*[AP]\\.?M\\.?/i;
    const stopsRe = /nonstop|non-stop|direct|(\\d+)\\s*stop|stop\\(s\\)|connecting/i;

    function normalize(t) {
        return (t || '').replace(/\\s+/g, ' ').trim();
    }

    const seen = new Set();
    const rows = [];

    function addRow(text) {
        const n = normalize(text);
        if (n.length < 15 || n.length > 4000) return;
        if (!priceRe.test(n)) return;
        if (!timeRe.test(n) && !stopsRe.test(n)) return;
        const key = n.slice(0, 120);
        if (seen.has(key)) return;
        seen.add(key);
        rows.push(n);
    }

    const main = document.querySelector('[role="main"]')
        || document.querySelector('main')
        || document.querySelector('#main')
        || document.body;

    const rowSelectors = [
        'li[role="listitem"]',
        '[role="listitem"]',
        '[data-testid*="result"]',
        '[data-testid*="flight"]',
        '[data-testid*="itinerary"]',
        '[data-testid*="fare"]',
        '[data-qa*="flight"]',
        '[data-qa*="result"]',
        '[class*="FlightResult"]',
        '[class*="flight-result"]',
        '[class*="flight-card"]',
        '[class*="FlightCard"]',
        '[class*="ResultCard"]',
        '[class*="FlightsTicket"]',
        '[class*="result"]',
        '[class*="itinerary"]',
        '[class*="fare-row"]',
        'button[class*="fare"]',
        'article',
        'table tbody tr',
    ];

    for (const sel of rowSelectors) {
        try {
            main.querySelectorAll(sel).forEach((el) => addRow(el.innerText || ''));
        } catch (e) { }
    }

    if (rows.length < 4) {
        const divs = main.querySelectorAll('div');
        divs.forEach((el) => {
            const n = normalize(el.innerText || '');
            if (n.length < 40 || n.length > 2000) return;
            if (!priceRe.test(n)) return;
            const kids = el.querySelectorAll('div, span');
            let innerPrice = 0;
            kids.forEach((k) => { if (priceRe.test(k.innerText || '')) innerPrice++; });
            if (innerPrice > 2) return;
            addRow(n);
        });
    }

    return rows.slice(0, 40);
}
"""

_FLIGHT_LINK_EXTRACTOR = """
() => {
    const out = [];
    const seen = new Set();
    const skip = /^(javascript:|#)/i;

    for (const a of document.querySelectorAll('a[href]')) {
        let href = a.getAttribute('href') || '';
        if (!href || skip.test(href)) continue;
        try {
            const u = new URL(href, window.location.href);
            href = u.href;
        } catch (e) { continue; }
        const text = (a.getAttribute('aria-label') || a.innerText || '').trim();
        const lower = (text + ' ' + href).toLowerCase();
        const flighty = /flight|book|select|continue|fare|\\$|price|itinerary|airline/.test(lower)
            || /\\/flights\\//.test(href);
        if (!flighty) continue;
        if (seen.has(href)) continue;
        seen.add(href);
        out.push({ href, label: text.slice(0, 120) });
        if (out.length >= 40) break;
    }
    return out;
}
"""


class PlaywrightProvider(ScrapingProvider):
    def __init__(self, base_url: str = "", api_key: Optional[str] = None):
        super().__init__(base_url, api_key)
        self.browser = None
        self._context = None
        self._lock = anyio.Lock()
        self._playwright = None
        self._context_created = False

    @staticmethod
    async def _random_delay(min_ms: float = 600, max_ms: float = 2200):
        if _FAST_MODE:
            return
        await anyio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))

    @staticmethod
    def _random_user_agent() -> str:
        return random.choice(_USER_AGENTS)

    @staticmethod
    def _random_viewport() -> "ViewportSize":
        return random.choice(_VIEWPORTS)

    @staticmethod
    def _host_content_selectors(url: str) -> list[str]:
        """Return extra wait/extraction selectors for known airline and aggregator hosts."""
        host = ""
        try:
            host = urlsplit(url).netloc.lower().removeprefix("www.")
        except Exception:
            pass
        extra: list[str] = []
        for domain, selectors in {**_AGGREGATOR_HOST_HINTS, **_AIRLINE_HOST_HINTS}.items():
            if domain in host:
                extra.extend(selectors)
        return extra

    def _check_playwright_installed(self) -> bool:
        try:
            import playwright
            return True
        except ImportError:
            return False

    async def _get_browser(self):
        if not self._playwright:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()

        if not self.browser or not self.browser.is_connected():
            with anyio.fail_after(_BROWSER_LAUNCH_TIMEOUT_SEC):
                self.browser = await self._playwright.chromium.launch(
                    headless=_HEADLESS, args=_STEALTH_ARGS
                )

        return self.browser

    async def _get_context(self):
        async with self._lock:
            if self._context is None:
                with anyio.fail_after(30):
                    self._context = await self._init_context()
            return self._context

    async def _init_context(self):
        """Initialize the persistent browser context. Caller must hold _lock."""
        browser = await self._get_browser()
        with anyio.fail_after(15):
            ctx = await browser.new_context(
                user_agent=self._random_user_agent(),
                viewport=self._random_viewport(),
                locale="en-US",
                timezone_id="America/New_York",
                color_scheme="light",
                reduced_motion="no-preference",
                device_scale_factor=random.choice([1, 2]),
                is_mobile=False,
                has_touch=False,
                permissions=["geolocation"],
                geolocation=_DEFAULT_GEOLOCATION,
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
        await ctx.add_init_script(_STEALTH_INIT_SCRIPT)
        self._context_created = True
        return ctx

    async def _human_scroll(self, page, steps: int = 4):
        """Scroll in small random increments like a human reading."""
        if _FAST_MODE:
            steps = min(steps, 2)
        for _ in range(steps):
            delta = random.randint(200, 500)
            try:
                await page.evaluate(f"window.scrollBy(0, {delta})")
            except Exception:
                break
            await self._random_delay(400, 1200)

    async def scrape(self, url: str) -> Dict[str, Any]:
        if not self._check_playwright_installed():
            return {"success": False, "error": "Playwright not installed"}

        print(f"[Playwright] Scraping: {url}")

        async with _page_semaphore:
            try:
                with anyio.fail_after(_PAGE_TOTAL_TIMEOUT_SEC):
                    return await self._scrape_page(url)
            except TimeoutError:
                print(f"[Playwright] Scrape timed out after {_PAGE_TOTAL_TIMEOUT_SEC}s: {url[:80]}")
                return {"success": False, "error": f"Scrape timed out after {_PAGE_TOTAL_TIMEOUT_SEC}s"}

    async def _scrape_page(self, url: str) -> Dict[str, Any]:
        page = None
        nav_timeout = _NAV_TIMEOUT_MS

        try:
            context = await self._get_context()
            with anyio.fail_after(15):
                page = await context.new_page()

            response_status = None
            # Fast mode: domcontentloaded first (much faster than networkidle).
            if _FAST_MODE:
                try:
                    response = await page.goto(
                        url, wait_until="domcontentloaded", timeout=10000
                    )
                    response_status = response.status if response else None
                    print(f"[Playwright] Status: {response_status} (domcontentloaded)")
                    await anyio.sleep(1.5)
                except Exception as e:
                    print(f"[Playwright] domcontentloaded failed: {e}")
            else:
                gw_timeout = nav_timeout
                try:
                    response = await page.goto(
                        url, wait_until="networkidle", timeout=gw_timeout
                    )
                    response_status = response.status if response else None
                    print(f"[Playwright] Status: {response_status} (networkidle)")
                except Exception as e:
                    print(
                        f"[Playwright] networkidle failed ({e}), falling back to domcontentloaded"
                    )
                    try:
                        response = await page.goto(
                            url, wait_until="domcontentloaded", timeout=8000
                        )
                        response_status = response.status if response else None
                        print(f"[Playwright] Status: {response_status} (domcontentloaded)")
                    except Exception as e2:
                        print(f"[Playwright] domcontentloaded also failed: {e2}")

            # ── WAIT FOR CONTENT ───────────────────────────────────────────────────
            # Give SPAs extra time to render flight results after navigation.
            content_selectors = [
                '[class*="price"]', '[data-testid*="price"]', '[data-qa*="price"]',
                '[class*="result"]', '[class*="flight"]', '[class*="fare"]',
                '[class*="itinerary"]', '[role="listitem"]',
                'table', 'article',
            ]
            host_selectors = self._host_content_selectors(url)
            if host_selectors:
                content_selectors = host_selectors + content_selectors
            found_selector = None
            host = (urlsplit(url).netloc or "").lower()
            is_airline = any(d in host for d in _AIRLINE_HOST_HINTS)
            selector_timeout = 8000 if is_airline else 3000
            for sel in content_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=selector_timeout)
                    found_selector = sel
                    print(f"[Playwright] Content selector found: {sel}")
                    break
                except Exception:
                    pass
            if not found_selector:
                wait_sec = 12 if is_airline else 2
                await anyio.sleep(wait_sec)
            elif is_airline:
                await anyio.sleep(5)

            # Copa / Aeromexico: query params pre-fill the form but do not run search.
            if is_airline and "origin=" in (page.url or url).lower():
                if "copaair.com" in host:
                    try:
                        search_btn = page.get_by_role(
                            "button", name=re.compile(r"^search$", re.I)
                        )
                        await search_btn.first.click(timeout=8000)
                        print("[Playwright] Copa: clicked SEARCH")
                        await anyio.sleep(10)
                    except Exception as exc:
                        print(f"[Playwright] Copa SEARCH click skipped: {exc}")
                elif "aeromexico.com" in host:
                    try:
                        search_btn = page.locator(
                            'button:has-text("Search"), [type="submit"]'
                        )
                        await search_btn.first.click(timeout=8000)
                        print("[Playwright] Aeromexico: clicked search")
                        await anyio.sleep(10)
                    except Exception as exc:
                        print(f"[Playwright] Aeromexico search click skipped: {exc}")

            # Google Flights: wait until fare list hydrates (not just shell)
            current_url = page.url or url
            if "google.com" in current_url.lower() and "/travel/flights" in current_url.lower():
                try:
                    await page.wait_for_function(
                        """() => {
                            const t = document.body?.innerText || '';
                            return t.includes('results returned')
                                || /\\$\\s*\\d{2,4}/.test(t)
                                || /US\\$\\s*[\\d,]+/.test(t);
                        }""",
                        timeout=12000,
                    )
                    print("[Playwright] Google Flights results loaded")
                except Exception:
                    await anyio.sleep(3)

            # ── CHALLENGE DETECTION ────────────────────────────────────────────────
            # Quick check using only URL and title (no body evaluate). In fast mode
            # we skip straight to content extraction — the service layer's
            # _classify_blocked_page does the heavy detection on the markdown.
            # In normal mode, poll briefly for challenge resolution.
            page_url = page.url
            page_title = ""
            challenge_detected = False
            try:
                page_title = await page.title()
            except Exception:
                pass

            challenge_url_patterns = [
                "__cf_chl_rt", "__cf_chl_ctx", "cdn-cgi/challenge-platform",
                "cloudflare.com/cdn-cgi/", "_cf_dns", "cf-ray",
                "/.well-known/cf-challenge",
            ]
            challenge_title_patterns = [
                "just a moment", "checking your browser", "attention required",
                "please verify", "cloudflare", "security check",
                "pardon our interruption", "suspended site",
            ]

            url_lower = page_url.lower()
            title_lower = page_title.lower()
            url_hit = any(p in url_lower for p in challenge_url_patterns)
            title_hit = any(p in title_lower for p in challenge_title_patterns)
            challenge_detected = url_hit or title_hit

            if challenge_detected and not _FAST_MODE:
                print(f"[Playwright] Challenge detected, polling for resolution (title='{page_title}')")
                for _ in range(10):
                    await anyio.sleep(1)
                    try:
                        page_url = page.url
                        page_title = await page.title()
                        url_lower = page_url.lower()
                        title_lower = page_title.lower()
                        still = any(p in url_lower for p in challenge_url_patterns) or \
                                any(p in title_lower for p in challenge_title_patterns)
                        if not still:
                            challenge_detected = False
                            print(f"[Playwright] Challenge resolved (title='{page_title}')")
                            break
                    except Exception:
                        pass
                else:
                    print(f"[Playwright] Challenge not resolved after 10s, giving up")

            if challenge_detected:
                await page.close()
                page = None
                return {
                    "success": False,
                    "error": "Challenge page detected",
                    "data": {
                        "markdown": f"CHALLENGE PAGE: {page_title}",
                        "flight_links": [],
                        "flight_row_texts": [],
                        "page_url": page_url,
                        "page_title": page_title,
                        "response_status": response_status,
                        "structured_prices": [],
                        "flight_link_details": [],
                    },
                }

            # ── CONTENT EXTRACTION ────────────────────────────────────────────────
            # Run all evaluate calls in parallel for speed.
            scroll_steps = 1 if _FAST_MODE else random.randint(3, 6)
            await self._human_scroll(page, steps=scroll_steps)

            try:
                await page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass

            try:
                split = urlsplit(page_url)
                if split.fragment:
                    page_url = urlunsplit(
                        (split.scheme, split.netloc, split.path, split.query, "")
                    )
            except Exception:
                pass

            title = page_title

            price_task = page.evaluate("""
                () => {
                    const prices = [];
                    const selectors = [
                        '[data-testid*="price"]', '[data-qa*="price"]',
                        '[class*="price"]', '[class*="fare"]',
                        '[aria-label*="price"]'
                    ];
                    for (const sel of selectors) {
                        const els = document.querySelectorAll(sel);
                        els.forEach(el => {
                            const text = el.textContent?.trim();
                            if (text && (text.includes('$') || text.match(/\\d+/))) {
                                prices.push({sel, text: text.substring(0, 80)});
                            }
                        });
                    }
                    return prices.slice(0, 30);
                }
            """)
            rows_task = page.evaluate(_FLIGHT_ROW_EXTRACTOR)
            links_task = page.evaluate(_FLIGHT_LINK_EXTRACTOR)

            structured_prices, flight_row_texts, link_objs = await gather(
                price_task, rows_task, links_task
            )

            if not link_objs:
                fallback_links = await page.evaluate("""
                    () => [...document.querySelectorAll('a[href]')]
                        .map(a => a.href)
                        .filter(h => h.startsWith('http') && h.length < 500)
                        .slice(0, 20)
                """)
                link_objs = [{"href": h} for h in fallback_links]

            flight_links = [o.get("href", "") for o in link_objs]

            text_content = await page.evaluate("""
                () => {
                    const root = document.querySelector('[role="main"]')
                        || document.querySelector('main')
                        || document.body;
                    const walker = document.createTreeWalker(
                        root,
                        NodeFilter.SHOW_TEXT,
                        { acceptNode: (node) =>
                            (node.parentElement?.tagName !== 'SCRIPT' &&
                             node.parentElement?.tagName !== 'STYLE' &&
                             node.parentElement?.tagName !== 'NOSCRIPT' &&
                             node.textContent?.trim().length > 0 &&
                             node.parentElement?.tagName !== 'HEADER' &&
                             !node.parentElement?.className?.includes('header') &&
                             !node.parentElement?.className?.includes('nav')) ?
                              NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT
                        }
                    );
                    let text = '';
                    let node;
                    while (node = walker.nextNode()) {
                        text += node.textContent.trim() + '\\n';
                    }
                    return text;
                }
            """)

            if flight_row_texts:
                row_sections = "\n\n".join(
                    f"--- Row {i + 1} ---\n{t}"
                    for i, t in enumerate(flight_row_texts)
                )
                merged = (
                    "Each --- Row N --- block is one UI result; pair price, times, stops, and airline only within that block.\n\n"
                    + row_sections
                    + "\n\n--- Full page text (may duplicate rows; prefer Row blocks above) ---\n\n"
                    + text_content
                )
            else:
                merged = text_content

            print(
                f"[Playwright] Got {len(merged)} chars (rows={len(flight_row_texts)}), "
                f"{len(flight_links)} links, url={page_url}"
            )

            if len(merged.strip()) < 50:
                return {"success": False, "error": "Empty or minimal content received"}

            return {
                "success": True,
                "data": {
                    "markdown": merged,
                    "flight_links": flight_links,
                    "flight_row_texts": flight_row_texts,
                    "page_url": page_url,
                    "page_title": title,
                    "response_status": response_status,
                    "structured_prices": structured_prices,
                    "flight_link_details": link_objs,
                },
            }

        except Exception as e:
            err = str(e)
            print(f"[Playwright] Error: {err}")
            if "Executable doesn't exist" in err or "playwright install" in err.lower():
                return {
                    "success": False,
                    "error": "Playwright browsers not installed. Run: playwright install chromium",
                }
            return {"success": False, "error": err}

        finally:
            if page:
                try:
                    with anyio.fail_after(5):
                        await page.close()
                except Exception:
                    pass

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        return []

    async def crawl(self, urls: List[str]) -> List[Dict[str, Any]]:
        results = []
        for url in urls:
            result = await self.scrape(url)
            results.append({"url": url, **result})
        return results

    async def close(self):
        if self._context:
            await self._context.close()
            self._context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
