"""Maps source name → scraper instance. Add new scrapers here."""
from __future__ import annotations

from .base import BaseScraper
from .dailyremote import DailyRemoteScraper
from .freelance_de import FreelanceDeScraper
from .freelancermap import FreelancermapScraper
from .indeed import IndeedScraper
from .linkedin import LinkedInScraper
from .nodesk import NoDeskScraper
from .stepstone import StepstoneScraper
from .weworkremotely import WeWorkRemotelyScraper
from .working_nomads import WorkingNomadsScraper
from .xing import XingScraper

REGISTRY: dict[str, BaseScraper] = {
    "weworkremotely": WeWorkRemotelyScraper(),
    "working_nomads": WorkingNomadsScraper(),
    "nodesk":         NoDeskScraper(),
    "dailyremote":    DailyRemoteScraper(),
    "freelancermap":  FreelancermapScraper(),
    "freelance_de":   FreelanceDeScraper(),
    "indeed":         IndeedScraper(),
    "stepstone":      StepstoneScraper(),
    "xing":           XingScraper(),
    "linkedin":       LinkedInScraper(),
}


def get_scraper(name: str) -> BaseScraper:
    if name not in REGISTRY:
        raise KeyError(f"unknown scraper: {name}")
    return REGISTRY[name]
