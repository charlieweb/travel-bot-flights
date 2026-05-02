import asyncio
import random
from typing import List, Dict, Any, Optional
from .base import ScrapingProvider

class PlaywrightProvider(ScrapingProvider):
    def __init__(self, base_url: str = "", api_key: Optional[str] = None):
        super().__init__(base_url, api_key)
        self.browser = None
        self._lock = asyncio.Lock()
        self._playwright = None

    def _check_playwright_installed(self) -> bool:
        try:
            import playwright
            return True
        except ImportError:
            return False

    async def _get_browser(self):
        """Get or create browser instance."""
        async with self._lock:
            if not self._playwright:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()

            if not self.browser or not self.browser.is_connected():
                self.browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-gpu",
                    ]
                )

            return self.browser

    async def scrape(self, url: str) -> Dict[str, Any]:
        """Scrape a URL and return content."""
        if not self._check_playwright_installed():
            return {"success": False, "error": "Playwright not installed"}

        print(f"[Playwright] Scraping: {url}")

        page = None
        context = None
        browser = None

        try:
            browser = await self._get_browser()

            # Create fresh context for each request
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="America/New_York",
            )

            page = await context.new_page()

            # Apply stealth
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                window.chrome = { runtime: {} };
            """)

            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
            })

            # Navigate
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                print(f"[Playwright] Status: {response.status if response else 'no response'}")
            except Exception as e:
                print(f"[Playwright] Nav error: {e}")
                try:
                    await page.goto(url, wait_until="commit", timeout=15000)
                except Exception as e2:
                    print(f"[Playwright] Fallback nav failed: {e2}")

            # Wait for page to settle
            await asyncio.sleep(2)

            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except:
                pass

            # Scroll to trigger lazy loading
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)
                await page.evaluate("window.scrollTo(0, 0)")
            except:
                pass

            # Get page title
            try:
                title = await page.title()
                print(f"[Playwright] Page title: {title}")
            except:
                pass

            # Extract text content
            text_content = await page.evaluate("""
                () => {
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        { acceptNode: (node) => 
                            (node.parentElement?.tagName !== 'SCRIPT' && 
                             node.parentElement?.tagName !== 'STYLE' &&
                             node.parentElement?.tagName !== 'NOSCRIPT' &&
                             node.textContent?.trim().length > 0) ? 
                              NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT 
                        }
                    );
                    let text = '';
                    let node;
                    while (node = walker.nextNode()) {
                        text += node.textContent.trim() + ' ';
                    }
                    return text;
                }
            """)

            # Extract links
            flight_links = await page.evaluate("""
                () => {
                    return [...document.querySelectorAll('a[href]')]
                        .map(a => a.href)
                        .filter(h => h.startsWith('http') && h.length < 250)
                        .slice(0, 15);
                }
            """)

            print(f"[Playwright] Got {len(text_content)} chars, {len(flight_links)} links")

            if len(text_content.strip()) < 50:
                return {"success": False, "error": "Empty or minimal content received"}

            return {
                "success": True,
                "data": {
                    "markdown": text_content,
                    "flight_links": flight_links
                }
            }

        except Exception as e:
            print(f"[Playwright] Error: {e}")
            return {"success": False, "error": str(e)}

        finally:
            if page:
                await page.close()
            if context:
                await context.close()

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        return []

    async def crawl(self, urls: List[str]) -> List[Dict[str, Any]]:
        results = []
        for url in urls:
            result = await self.scrape(url)
            results.append({"url": url, **result})
        return results

    async def close(self):
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None