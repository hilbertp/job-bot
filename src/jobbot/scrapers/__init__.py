"""Scrapers, one module per source. All implement BaseScraper.fetch()."""
from .base import BaseScraper, SearchQuery
from .registry import REGISTRY, get_scraper

__all__ = ["BaseScraper", "SearchQuery", "REGISTRY", "get_scraper"]
