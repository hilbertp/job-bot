"""Maps source name → scraper instance. Add new scrapers here."""
from __future__ import annotations

from .base import BaseScraper
from .dailyremote import DailyRemoteScraper
from .freelance_de import FreelanceDeScraper
from .braintrust import BraintrustScraper
from .builtin import BuiltInScraper
from .brainville import BrainvilleScraper
from .free_work import FreeWorkScraper
from .freelancermap import FreelancermapScraper
from .himalayas import HimalayasScraper
from .indeed import IndeedScraper
from .jobgether import JobgetherScraper
from .linkedin import LinkedInScraper
from .nodesk import NoDeskScraper
from .remoteok import RemoteOkScraper
from .remoterocketship import RemoteRocketshipScraper
from .remotive import RemotiveScraper
from .stepstone import StepstoneScraper
from .talentmate import TalentmateScraper
from .weworkremotely import WeWorkRemotelyScraper
from .wellfound import WellfoundScraper
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
    "talentmate":     TalentmateScraper(),
    "xing":           XingScraper(),
    "linkedin":       LinkedInScraper(),
    "remotive":       RemotiveScraper(),
    "remoteok":       RemoteOkScraper(),
    "himalayas":      HimalayasScraper(),
    "free_work":      FreeWorkScraper(),
    "braintrust":     BraintrustScraper(),
    "brainville":     BrainvilleScraper(),
    # Remote PM/PO boards added 2026-09-17 after the source audit.
    "remoterocketship": RemoteRocketshipScraper(),
    "jobgether":      JobgetherScraper(),
    "wellfound":      WellfoundScraper(),
    "builtin":        BuiltInScraper(),
}


def get_scraper(name: str) -> BaseScraper:
    if name not in REGISTRY:
        raise KeyError(f"unknown scraper: {name}")
    return REGISTRY[name]
