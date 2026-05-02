"""
Provider factory and exports.

Usage:
from services.scraping.providers import get_provider

provider = get_provider("spider")
# or
provider = get_provider() # Uses SCRAPING_PROVIDER env var
"""

import os
from typing import Optional

if os.getenv("SCRAPING_PROVIDER") is None:
    from dotenv import load_dotenv
    load_dotenv()

from .base import ScrapingProvider
from .spider import SpiderCloudProvider
from .playwright_provider import PlaywrightProvider


def get_provider(
    provider_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> ScrapingProvider:
    """Factory function to get the appropriate scraping provider."""
    provider = (provider_name or os.getenv("SCRAPING_PROVIDER", "spider")).lower()

    if provider == "spider":
        return SpiderCloudProvider(
            base_url=base_url or "https://api.spider.cloud",
            api_key=api_key or os.getenv("SPIDER_API_KEY")
        )
    elif provider == "playwright":
        return PlaywrightProvider(
            base_url=base_url or os.getenv("PLAYWRIGHT_CDP_URL", "http://localhost:9222"),
            api_key=api_key
        )
    else:
        raise ValueError(f"Unknown provider: {provider}. Supported: spider, playwright")


__all__ = [
    "ScrapingProvider",
    "SpiderCloudProvider",
    "PlaywrightProvider",
    "get_provider"
]