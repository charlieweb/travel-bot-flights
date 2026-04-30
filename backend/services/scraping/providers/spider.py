"""
Spider Cloud API provider implementation.

Cloud-based scraping service with excellent JS rendering.
API documentation: https://spider.cloud/docs

Free credits on signup - no credit card required.
"""

import httpx
from typing import List, Dict, Any, Optional

from .base import ScrapingProvider


class SpiderCloudProvider(ScrapingProvider):
    """
    Spider Cloud API provider.

    Uses Spider's cloud API for web scraping with superior JS rendering.
    Requires SPIDER_API_KEY for authentication.

    Features:
    - Excellent JavaScript rendering (stealth browser)
    - Search endpoint for URL discovery
    - Multiple output formats (markdown, html, json)
    - Anti-bot bypass built-in

    Pricing: Pay per page, starting under a tenth of a cent
    Free credits on signup: https://spider.cloud/dashboard
    """

    BASE_URL = "https://api.spider.cloud"

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for URLs using Spider Cloud's search endpoint.
        """
        if not self.api_key:
            raise ValueError("Spider Cloud API key is required")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/search",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"search": query, "limit": limit},
            )
            response.raise_for_status()
            data = response.json()

            # Spider returns: { "content": [{ "url": "...", "title": "...", "description": "..." }] }
            results = []
            content = data.get("content", [])
            if isinstance(content, list):
                for item in content:
                    results.append({
                        "url": item.get("url", ""),
                        "title": item.get("title", ""),
                        "description": item.get("description", ""),
                    })

            return results[:limit]

    async def scrape(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single URL using Spider Cloud's scrape endpoint.
        """
        if not self.api_key:
            return {"success": False, "data": {}}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/scrape",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "return_format": "markdown",
                },
            )
            response.raise_for_status()
            data = response.json()

            # Spider returns a list: [{ "content": "...", "status": 200, "url": "..." }]
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                if item.get("status") == 200 and item.get("content"):
                    return {
                        "success": True,
                        "data": {
                            "markdown": item.get("content", ""),
                            "html": "",
                            "url": item.get("url", url),
                            "title": "",
                        }
                    }
                elif item.get("error"):
                    print(f"Spider error for {url}: {item.get('error')}")

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
        Scrape a URL after interacting with the page.
        """
        if not self.api_key:
            return {"success": False, "data": {}}

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/scrape",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "return_format": "markdown",
                },
            )
            response.raise_for_status()
            data = response.json()

            # Spider returns a list: [{ "content": "...", "status": 200, "url": "..." }]
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                if item.get("status") == 200 and item.get("content"):
                    return {
                        "success": True,
                        "data": {
                            "markdown": item.get("content", ""),
                            "html": "",
                            "url": item.get("url", url),
                            "title": "",
                        }
                    }
                elif item.get("error"):
                    print(f"Spider error for {url}: {item.get('error')}")

            return {"success": False, "data": {}}

    async def crawl(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl multiple URLs using Spider Cloud's crawl endpoint.
        """
        if not self.api_key:
            return [{"url": url, "markdown": "", "success": False} for url in urls]

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/crawl",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": urls[0] if len(urls) == 1 else urls,
                    "limit": len(urls),
                    "return_format": "markdown",
                },
            )
            response.raise_for_status()
            data = response.json()

            # Spider returns a list: [{ "content": "...", "status": 200, "url": "..." }]
            results = []
            if isinstance(data, list):
                for item in data:
                    if item.get("status") == 200 and item.get("content"):
                        results.append({
                            "url": item.get("url", ""),
                            "markdown": item.get("content", ""),
                            "success": True,
                        })
                    else:
                        results.append({
                            "url": item.get("url", ""),
                            "markdown": "",
                            "success": False,
                        })

            return results if results else [
                {"url": url, "markdown": "", "success": False} for url in urls
            ]