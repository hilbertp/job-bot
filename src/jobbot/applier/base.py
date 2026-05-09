"""Adapter interface — one per ATS (Greenhouse, Lever, Workday, etc.)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ..models import GeneratedDocs, JobPosting
from ..profile import Profile

if TYPE_CHECKING:
    from playwright.sync_api import Page


@runtime_checkable
class FormAdapter(Protocol):
    name: str

    def matches(self, url: str, page: "Page") -> bool:
        """Return True if this adapter knows how to handle the form on `page`."""
        ...

    def fill(self, page: "Page", job: JobPosting, profile: Profile, docs: GeneratedDocs) -> None:
        """Fill out all standard fields. Should not click submit."""
        ...

    def submit(self, page: "Page") -> str:
        """Click the final submit button. Return the URL of the confirmation page."""
        ...
