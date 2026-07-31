"""usebraintrust.com (US talent network), public DRF JSON API.

Verified 2026-07-17: https://app.usebraintrust.com/api/jobs/ is unauthenticated;
`search` filters server-side; pagination via `next` (returned as http://, force
https). Budget fields make US $150k-bar screening possible at fetch time.
"""
from __future__ import annotations

from datetime import datetime

import httpx
import structlog

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_API_URL = "https://app.usebraintrust.com/api/jobs/"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_MAX_PAGES = 3  # 20/page; keyword queries rarely need more


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


class BraintrustScraper(BaseScraper):
    source = "braintrust"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "product manager"}; server-side `search` param.
        out: list[JobPosting] = []
        url: str | None = _API_URL
        params: dict[str, str] | None = {"search": (query.get("q") or "product").strip(), "page": "1"}
        for _ in range(_MAX_PAGES):
            if not url:
                break
            try:
                r = httpx.get(url, params=params, headers={"User-Agent": _UA}, timeout=20.0)
                r.raise_for_status()
                data = r.json()
            except Exception as exc:
                log.warning("braintrust_fetch_failed", error=str(exc))
                break
            params = None  # `next` URLs already carry the query string
            for entry in data.get("results", []):
                jid = entry.get("id")
                title = entry.get("title") or ""
                if not jid or not title:
                    continue
                job_url = f"https://app.usebraintrust.com/jobs/{jid}/"
                employer = ((entry.get("employer") or {}).get("name")) or "Unknown"
                bmin, bmax = entry.get("budget_minimum_usd"), entry.get("budget_maximum_usd")
                ptype = entry.get("payment_type") or ""
                desc_bits = []
                if bmin or bmax:
                    desc_bits.append(f"Budget: {bmin or '?'} - {bmax or '?'} USD ({ptype})")
                tzs = [t.get("timezone") for t in (entry.get("timezones") or []) if isinstance(t, dict)]
                if tzs:
                    desc_bits.append("Timezones: " + ", ".join(filter(None, tzs)))
                skills = [s.get("name") for s in (entry.get("main_skills") or []) if isinstance(s, dict)]
                out.append(JobPosting(
                    id=stable_id(self.source, job_url),
                    source=self.source,
                    title=title.strip(),
                    company=employer.strip(),
                    location=", ".join(filter(None, tzs)) or "Remote (US network)",
                    url=job_url,
                    apply_url=job_url,
                    posted_at=_parse_dt(entry.get("created")),
                    description="\n".join(desc_bits),
                    tags=["remote", "freelance"] + [s for s in skills if s],
                ))
            nxt = data.get("next")
            url = nxt.replace("http://", "https://", 1) if nxt else None
        return out

    def fetch_detail(self, job: "JobPosting") -> JobPosting | None:
        """Fetch the JSON detail endpoint for the full description."""
        jid = str(job.url).rstrip("/").rsplit("/", 1)[-1]
        try:
            r = httpx.get(f"{_API_URL}{jid}/", headers={"User-Agent": _UA}, timeout=20.0)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return None
        desc = (data.get("description") or "").strip()
        merged = (job.description + "\n\n" + desc).strip()
        if len(merged.split()) < 100:
            return None
        return job.model_copy(update={"description": merged[:12000]})
