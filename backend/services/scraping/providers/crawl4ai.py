"""
Crawl4AI self-hosted provider implementation.

Supports Crawl4AI's /crawl endpoint for self-hosted instances with
browser automation for form submission and dynamic content.
"""

import httpx
from typing import List, Dict, Any, Optional

from .base import ScrapingProvider


AIRLINE_INTERACTION_SCRIPTS = {
    "delta": r"""
(function() {
    var originInput = document.querySelector('input[placeholder*="From"], input[id*="origin"], input[name*="origin"]');
    if (originInput) {
        originInput.value = '{origin}';
        originInput.dispatchEvent(new Event('input', { bubbles: true }));
        originInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
    setTimeout(function() {}, 500);

    var destInput = document.querySelector('input[placeholder*="To"], input[id*="destination"], input[name*="destination"]');
    if (destInput) {
        destInput.value = '{destination}';
        destInput.dispatchEvent(new Event('input', { bubbles: true }));
        destInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
    setTimeout(function() {}, 500);

    var dateInput = document.querySelector('input[type="date"], input[placeholder*="date"], input[id*="date"]');
    if (dateInput && '{date}') {
        dateInput.value = '{date}';
        dateInput.dispatchEvent(new Event('input', { bubbles: true }));
        dateInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    var searchBtn = document.querySelector('button[type="submit"]');
    if (searchBtn) {
        searchBtn.click();
    }
    setTimeout(function() {}, 3000);
})();
""",
    "united": r"""
(function() {
    var inputs = document.querySelectorAll('input');
    for (var i = 0; i < inputs.length; i++) {
        var input = inputs[i];
        var label = input.closest('label') ? input.closest('label').textContent.toLowerCase() : '';
        var placeholder = input.placeholder ? input.placeholder.toLowerCase() : '';
        var name = input.name ? input.name.toLowerCase() : '';

        if (label.indexOf('from') > -1 || placeholder.indexOf('from') > -1 || name.indexOf('origin') > -1) {
            input.value = '{origin}';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        if (label.indexOf('to') > -1 || placeholder.indexOf('to') > -1 || name.indexOf('dest') > -1) {
            input.value = '{destination}';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }
    setTimeout(function() {}, 500);

    var buttons = document.querySelectorAll('button');
    for (var i = 0; i < buttons.length; i++) {
        var text = buttons[i].textContent;
        if (text.indexOf('Search') > -1 || text.indexOf('Book') > -1) {
            buttons[i].click();
            break;
        }
    }
    setTimeout(function() {}, 3000);
})();
""",
    "american": r"""
(function() {
    var inputs = document.querySelectorAll('input');
    for (var i = 0; i < inputs.length; i++) {
        var input = inputs[i];
        if (input.id.indexOf('origin') > -1 || input.name.indexOf('origin') > -1) {
            input.value = '{origin}';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        if (input.id.indexOf('dest') > -1 || input.name.indexOf('dest') > -1) {
            input.value = '{destination}';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }
    setTimeout(function() {}, 500);

    var btn = document.querySelector('button[type="submit"]');
    if (btn) btn.click();
    setTimeout(function() {}, 3000);
})();
""",
    "generic": r"""
(function() {
    var inputs = document.querySelectorAll('input');
    for (var i = 0; i < inputs.length; i++) {
        var input = inputs[i];
        var placeholder = (input.placeholder || '').toLowerCase();
        var id = (input.id || '').toLowerCase();
        var name = (input.name || '').toLowerCase();
        var type = input.type || 'text';

        if (type === 'text' || type === 'search') {
            if (placeholder.indexOf('from') > -1 || id.indexOf('origin') > -1 || name.indexOf('origin') > -1) {
                input.value = '{origin}';
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
            if (placeholder.indexOf('to') > -1 || id.indexOf('dest') > -1 || name.indexOf('dest') > -1) {
                input.value = '{destination}';
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
            if (placeholder.indexOf('date') > -1 || id.indexOf('date') > -1) {
                input.value = '{date}';
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
    }
    setTimeout(function() {}, 500);

    var buttons = document.querySelectorAll('button');
    for (var i = 0; i < buttons.length; i++) {
        var text = buttons[i].textContent.toLowerCase();
        if (text.indexOf('search') > -1 || text.indexOf('find') > -1 || text.indexOf('book') > -1 || text.indexOf('submit') > -1) {
            buttons[i].click();
            break;
        }
    }
    setTimeout(function() {}, 3000);
})();
"""
}


def _format_js_script(script: str, origin: str, destination: str, date: str) -> str:
    """Replace placeholders in JS script using simple string replacement."""
    result = script.replace('{origin}', origin)
    result = result.replace('{destination}', destination)
    result = result.replace('{date}', date)
    return result


AIRLINE_WAIT_SELECTORS = {
    "delta": "css:.flight-card, css:.price-cell, css:[data-testid*='price'], css:.offer-price",
    "united": "css:.flight-option, css:.trip-price, css:[data-testid*='price']",
    "american": "css:.flight-card, css:.price-cell, css:[data-qa*='price']",
    "southwest": "css:.flight-card, css:.price-cell",
    "google": "css:.price, css:.flight-item, css[aria-label*='price']",
    "kayak": "css:.result-price, css:.price-frame, css[data-testid*='price']",
    "skyscanner": "css:.bp-listitem, css.itinerary-price",
    "generic": "css:.flight, css.price, css[data-testid*='result']"
}

DELAY_AFTER_WAIT = 3


class Crawl4AIProvider(ScrapingProvider):
    """
    Crawl4AI self-hosted provider.

    Uses Crawl4AI's REST API for web crawling with browser automation.
    Can be self-hosted via Docker (unclecode/crawl4ai).

    Documentation: https://docs.crawl4ai.com

    Note: Crawl4AI doesn't have a native search endpoint like Firecrawl.
    Search functionality should be handled at a higher level.
    """

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for URLs using Crawl4AI.

        Note: Crawl4AI doesn't have a search endpoint.
        Returns empty list - search must be handled separately
        (e.g., using Google Custom Search, Bing API, etc.)

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            Empty list (search not supported)
        """
        return []

    async def scrape(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single URL using Crawl4AI's crawl endpoint.

        Args:
            url: URL to scrape

        Returns:
            Dictionary normalized to Firecrawl format with markdown content

        Raises:
            httpx.HTTPError: If API request fails
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = await client.post(
                f"{self.base_url}/crawl",
                headers=headers,
                json={
                    "urls": [url],
                    "priority": 10,
                }
            )
            response.raise_for_status()
            data = response.json()

            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                return {
                    "success": True,
                    "data": {
                        "markdown": result.get("markdown", ""),
                        "html": result.get("html", ""),
                        "url": url,
                        "title": result.get("title", ""),
                    }
                }

            if "task_id" in data:
                task_id = data["task_id"]
                return await self._wait_for_task(client, task_id, url)

            return {"success": False, "data": {}}

    async def scrape_with_interaction(
        self,
        url: str,
        origin: str = "",
        destination: str = "",
        date: str = "",
        airline: str = ""
    ) -> Dict[str, Any]:
        """
        Scrape a URL after interacting with the page (filling forms, clicking buttons).

        This is needed for airline websites where flight search requires form submission.

        Args:
            url: URL to navigate to and interact with
            origin: Origin airport code
            destination: Destination airport code
            date: Departure date (YYYY-MM-DD)
            airline: Airline name to select appropriate interaction script

        Returns:
            Dictionary with markdown content from the results page
        """
        async with httpx.AsyncClient(timeout=180.0) as client:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            script_key = airline.lower() if airline else "generic"
            if script_key not in AIRLINE_INTERACTION_SCRIPTS:
                script_key = "generic"

            js_code = _format_js_script(
                AIRLINE_INTERACTION_SCRIPTS[script_key],
                origin=origin,
                destination=destination,
                date=date
            )

            wait_selector = self._get_wait_selector(airline)

            crawl_payload = {
                "urls": [url],
                "priority": 10,
                "js_code": [js_code],
                "wait_for": wait_selector,
                "delay_before_return_html": DELAY_AFTER_WAIT,
            }

            response = await client.post(
                f"{self.base_url}/crawl",
                headers=headers,
                json=crawl_payload
            )
            response.raise_for_status()
            data = response.json()

            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                return {
                    "success": True,
                    "data": {
                        "markdown": result.get("markdown", ""),
                        "html": result.get("html", ""),
                        "url": url,
                        "title": result.get("title", ""),
                    }
                }

            if "task_id" in data:
                task_id = data["task_id"]
                return await self._wait_for_task(client, task_id, url)

            return {"success": False, "data": {}}

    def _get_wait_selector(self, airline: str) -> str:
        """Get the appropriate CSS selector to wait for based on airline/aggregator name."""
        if not airline:
            return AIRLINE_WAIT_SELECTORS.get("generic", "css:.flight, css.price")

        airline_lower = airline.lower()
        for key, selector in AIRLINE_WAIT_SELECTORS.items():
            if key in airline_lower:
                return selector

        return AIRLINE_WAIT_SELECTORS["generic"]

    async def _wait_for_task(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        url: str
    ) -> Dict[str, Any]:
        """
        Wait for async crawl task to complete.

        Args:
            client: HTTPX client
            task_id: Crawl4AI task ID
            url: Original URL

        Returns:
            Normalized response with markdown
        """
        import asyncio

        max_retries = 30
        retry_delay = 2.0

        for _ in range(max_retries):
            response = await client.get(f"{self.base_url}/task/{task_id}")
            if response.status_code == 200:
                data = response.json()

                if "results" in data and len(data["results"]) > 0:
                    result = data["results"][0]
                    return {
                        "success": True,
                        "data": {
                            "markdown": result.get("markdown", ""),
                            "html": result.get("html", ""),
                            "url": url,
                            "title": result.get("title", ""),
                        }
                    }

            await asyncio.sleep(retry_delay)

        return {"success": False, "data": {}}

    async def crawl(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl multiple URLs using Crawl4AI.

        Args:
            urls: List of URLs to crawl

        Returns:
            List of crawl results
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = await client.post(
                f"{self.base_url}/crawl",
                headers=headers,
                json={
                    "urls": urls,
                    "priority": 10,
                }
            )
            response.raise_for_status()
            data = response.json()

            if "results" in data:
                return [
                    {
                        "url": result.get("url", urls[i] if i < len(urls) else ""),
                        "markdown": result.get("markdown", ""),
                        "success": True
                    }
                    for i, result in enumerate(data["results"])
                ]

            if "task_id" in data:
                task_id = data["task_id"]
                results = await self._wait_for_batch_task(client, task_id, urls)
                return results

            return [{"url": url, "markdown": "", "success": False} for url in urls]

    async def _wait_for_batch_task(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        urls: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Wait for batch crawl task to complete.

        Args:
            client: HTTPX client
            task_id: Crawl4AI task ID
            urls: Original URLs

        Returns:
            List of normalized results
        """
        import asyncio

        max_retries = 60
        retry_delay = 2.0

        for _ in range(max_retries):
            response = await client.get(f"{self.base_url}/task/{task_id}")
            if response.status_code == 200:
                data = response.json()

                if "results" in data:
                    return [
                        {
                            "url": result.get("url", urls[i] if i < len(urls) else ""),
                            "markdown": result.get("markdown", ""),
                            "success": True
                        }
                        for i, result in enumerate(data["results"])
                    ]

            await asyncio.sleep(retry_delay)

        return [{"url": url, "markdown": "", "success": False} for url in urls]