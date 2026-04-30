"""
Scraping service package for Travel Bot.

This package provides a unified interface for multiple web scraping providers:
- Firecrawl: Cloud-based API service
- Crawl4AI: Self-hosted open-source crawler

Usage:
    from services.scraping import ScrapingService
    
    service = ScrapingService()
    results = await service.search_travel_options(origin, destination, depart_date, return_date)
"""

from .service import ScrapingService

__all__ = ["ScrapingService"]
