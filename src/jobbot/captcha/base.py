"""CaptchaSolver interface + a no-op implementation for when no API key is set."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from playwright.sync_api import Page


class CaptchaSolver(Protocol):
    name: str

    def solve_recaptcha_v2(self, site_key: str, url: str) -> str | None: ...
    def solve_recaptcha_v3(self, site_key: str, url: str, action: str) -> str | None: ...
    def solve_hcaptcha(self, site_key: str, url: str) -> str | None: ...
    def solve_image(self, png_bytes: bytes) -> str | None: ...

    def solve_on_page(self, page: "Page", url: str) -> bool:
        """Detect captcha type on `page`, solve, inject token. Returns True on success."""
        ...


class NullSolver:
    """Used when no captcha provider is configured. Always returns failure — application
    will be marked needs-review."""
    name = "null"

    def solve_recaptcha_v2(self, *_): return None
    def solve_recaptcha_v3(self, *_): return None
    def solve_hcaptcha(self, *_):     return None
    def solve_image(self, *_):        return None

    def solve_on_page(self, page: "Page", url: str) -> bool:
        return False
