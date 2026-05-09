"""2Captcha — paid solver service. ~$2.99 per 1000 reCAPTCHAs."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from playwright.sync_api import Page

API = "https://2captcha.com"


class TwoCaptchaSolver:
    name = "twocaptcha"

    def __init__(self, api_key: str, timeout_s: int = 90) -> None:
        self.key = api_key
        self.timeout_s = timeout_s

    def _submit(self, params: dict) -> str:
        params["key"] = self.key
        params["json"] = "1"
        r = httpx.post(f"{API}/in.php", data=params, timeout=20).json()
        if r.get("status") != 1:
            raise RuntimeError(f"2captcha submit failed: {r}")
        return r["request"]

    def _poll(self, captcha_id: str) -> str | None:
        deadline = time.time() + self.timeout_s
        while time.time() < deadline:
            time.sleep(5)
            r = httpx.get(
                f"{API}/res.php",
                params={"key": self.key, "action": "get", "id": captcha_id, "json": 1},
                timeout=20,
            ).json()
            if r.get("status") == 1:
                return r["request"]
            if r.get("request") != "CAPCHA_NOT_READY":
                return None
        return None

    def solve_recaptcha_v2(self, site_key: str, url: str) -> str | None:
        cid = self._submit({"method": "userrecaptcha", "googlekey": site_key, "pageurl": url})
        return self._poll(cid)

    def solve_recaptcha_v3(self, site_key: str, url: str, action: str = "verify") -> str | None:
        cid = self._submit({"method": "userrecaptcha", "version": "v3",
                            "googlekey": site_key, "pageurl": url, "action": action,
                            "min_score": "0.7"})
        return self._poll(cid)

    def solve_hcaptcha(self, site_key: str, url: str) -> str | None:
        cid = self._submit({"method": "hcaptcha", "sitekey": site_key, "pageurl": url})
        return self._poll(cid)

    def solve_image(self, png_bytes: bytes) -> str | None:
        import base64
        cid = self._submit({"method": "base64", "body": base64.b64encode(png_bytes).decode()})
        return self._poll(cid)

    def solve_on_page(self, page: "Page", url: str) -> bool:
        # reCAPTCHA v2
        v2 = page.locator("div.g-recaptcha[data-sitekey]")
        if v2.count() > 0:
            site_key = v2.first.get_attribute("data-sitekey") or ""
            token = self.solve_recaptcha_v2(site_key, url)
            if not token:
                return False
            page.evaluate("token => { document.querySelector('#g-recaptcha-response').value = token; }", token)
            return True
        # hCaptcha
        h = page.locator("div.h-captcha[data-sitekey]")
        if h.count() > 0:
            site_key = h.first.get_attribute("data-sitekey") or ""
            token = self.solve_hcaptcha(site_key, url)
            if not token:
                return False
            page.evaluate("token => { document.querySelector('[name=h-captcha-response]').value = token; }", token)
            return True
        return True  # nothing to solve
