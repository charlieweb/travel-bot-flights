"""
Scraping service package for Travel Bot.

Providers: Spider Cloud, Playwright.
Parsing: regex-first in service.py, Gemini fallback in ai_parser.py.

Usage:
    from services.scraping import ScrapingService

    service = ScrapingService()
    results = await service.search_travel_options(
        origin, destination, depart_date, return_date
    )
"""

from .service import ScrapingService

__all__ = ["ScrapingService"]
