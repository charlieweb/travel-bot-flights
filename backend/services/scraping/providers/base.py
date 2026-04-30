"""
Abstract base class for scraping providers.

Defines the interface that all scraping providers must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class ScrapingProvider(ABC):
    """
    Abstract base class for scraping providers.
    
    All providers (Firecrawl, Crawl4AI, etc.) must implement this interface
to ensure consistent behavior across different scraping services.
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize the provider with configuration.
        
        Args:
            base_url: The base URL for the provider's API
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
    
    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for URLs related to a query.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of search results with 'url', 'title', etc.
        """
        pass
    
    @abstractmethod
    async def scrape(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single URL and return markdown content.
        
        Args:
            url: URL to scrape
            
        Returns:
            Dictionary with 'markdown', 'html', 'success', etc.
        """
        pass
    
    @abstractmethod
    async def crawl(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl multiple URLs.
        
        Args:
            urls: List of URLs to crawl
            
        Returns:
            List of crawl results
        """
        pass
