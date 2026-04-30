"""
Provider factory and exports.

Usage:
    from services.scraping.providers import get_provider

    provider = get_provider("firecrawl")
    # or
    provider = get_provider()  # Uses SCRAPING_PROVIDER env var
"""

import os
from typing import Optional

from .base import ScrapingProvider
from .firecrawl import FirecrawlProvider
from .crawl4ai import Crawl4AIProvider
from .spider import SpiderCloudProvider


def get_provider(
    provider_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> ScrapingProvider:
    """
    Factory function to get the appropriate scraping provider.

    Args:
        provider_name: Provider type ('firecrawl', 'crawl4ai', or 'spider').
                      Defaults to SCRAPING_PROVIDER env var or 'firecrawl'.
        base_url: Provider base URL. Defaults to env var or provider default.
        api_key: API key for authentication. Defaults to env var.

    Returns:
        ScrapingProvider instance configured with appropriate settings.

    Raises:
        ValueError: If provider_name is unknown.

    Example:
        >>> provider = get_provider("firecrawl")
        >>> provider = get_provider("crawl4ai")
        >>> provider = get_provider("spider")
    """
    provider = (provider_name or os.getenv("SCRAPING_PROVIDER", "firecrawl")).lower()

    if provider == "firecrawl":
        return FirecrawlProvider(
            base_url=base_url or os.getenv(
                "FIRECRAWL_BASE_URL",
                "https://api.firecrawl.dev/v2"
            ),
            api_key=api_key or os.getenv("FIRECRAWL_API_KEY")
        )
    elif provider == "crawl4ai":
        return Crawl4AIProvider(
            base_url=base_url or os.getenv(
                "CRAWL4AI_BASE_URL",
                "http://crawl4ai:11235"
            ),
            api_key=api_key or os.getenv("CRAWL4AI_API_TOKEN") or None
        )
    elif provider == "spider":
        return SpiderCloudProvider(
            base_url=base_url or "https://api.spider.cloud",
            api_key=api_key or os.getenv("SPIDER_API_KEY")
        )
    else:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Supported providers: firecrawl, crawl4ai, spider"
        )


__all__ = [
    "ScrapingProvider",
    "FirecrawlProvider",
    "Crawl4AIProvider",
    "SpiderCloudProvider",
    "get_provider"
]
