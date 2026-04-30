"""
Firecrawl cloud API provider implementation.

Supports Firecrawl's search, scrape, and crawl endpoints.
"""

import httpx
from typing import List, Dict, Any, Optional

from .base import ScrapingProvider


class FirecrawlProvider(ScrapingProvider):
    """
    Firecrawl cloud API provider.
    
    Uses Firecrawl's REST API for web search and scraping.
    Requires FIRECRAWL_API_KEY for authentication.
    
    Documentation: https://docs.firecrawl.dev
    """
    
    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for URLs using Firecrawl's search endpoint.
        
        Args:
            query: Search query (e.g., "flights from JFK to LAX")
            limit: Maximum number of results
            
        Returns:
            List of search results with url, title, description, etc.
            
        Raises:
            httpx.HTTPError: If API request fails
        """
        if not self.api_key:
            raise ValueError("Firecrawl API key is required")
            
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/search",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"query": query, "limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                return data.get("data", {}).get("web", [])
            return []
    
    async def scrape(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single URL using Firecrawl's scrape endpoint.
        
        Args:
            url: URL to scrape
            
        Returns:
            Dictionary with markdown content and metadata
            
        Raises:
            httpx.HTTPError: If API request fails
        """
        if not self.api_key:
            raise ValueError("Firecrawl API key is required")
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/scrape",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "url": url,
                    "formats": ["markdown", "html"],
                    "onlyMainContent": True,
                    "waitFor": 3000,
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def crawl(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl multiple URLs using Firecrawl's crawl endpoint.
        
        Note: Firecrawl's crawl endpoint works differently than scrape.
        For multiple URLs, we use parallel scrape requests.
        
        Args:
            urls: List of URLs to crawl
            
        Returns:
            List of crawl results
        """
        # For Firecrawl, use parallel scrape requests
        results = []
        for url in urls:
            try:
                result = await self.scrape(url)
                if result.get("success"):
                    results.append({
                        "url": url,
                        "markdown": result.get("data", {}).get("markdown", ""),
                        "success": True
                    })
            except Exception:
                results.append({
                    "url": url,
                    "markdown": "",
                    "success": False
                })
        return results
