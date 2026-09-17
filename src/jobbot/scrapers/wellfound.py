"""wellfound.com (formerly AngelList Talent), startup jobs, mostly remote.

List page: https://wellfound.com/role/r/<role-slug>. Both
/role/r/product-manager and /role/r/product-owner exist (measured
2026-09-17: HTTP 200, 677 KB with 46 jobs and 399 KB with 24 jobs). The
page is Next.js. Its <script id="__NEXT_DATA__"> JSON holds an Apollo
cache at props.pageProps.apolloState.data with one
"JobListingSearchResult:<id>" entry per card: id, slug, title, remote,
locationNames, compensation (a string such as "$158k to $200k", written
with an en-dash on the site, often empty), liveStartAt (epoch seconds,
equal to the detail page's datePosted) and the description as markdown.
The company name sits on "StartupResult:<id>" entries, which point at
their jobs through highlightedJobListings. The role page also shows
sibling roles of the same startups (Onboarding Specialist, Engineering
Manager), so titles are filtered against the query here. Without the
JSON, the href="/jobs/<id>-<slug>" anchors are the fallback.

Detail page: https://wellfound.com/jobs/<id>-<slug>, public, no login
wall for reading. One JSON-LD JobPosting block with datePosted,
hiringOrganization.name, description (HTML), jobLocation and baseSalary.
The visible header reads "Product Manager $158k to $200k | Remote
( Everywhere ) | Full Time Posted: 3 years ago". A made-up id answers
404. Applying needs an account, so apply_url is the job URL itself.

Freshness rule, and why: Wellfound keeps very old listings visible (job
2644195, posted 2023-04-14, was still served on 2026-09-17). A row that
old is not an opening, and retrying it every run is waste. So a listing
posted more than 30 days ago is skipped in fetch and raises ListingGone
in fetch_detail, which marks the row listing_expired for good.

Cloudflare fronts the site. A 403 or a "Just a moment" body is a block,
not a verdict on the posting: fetch returns [] and fetch_detail returns
None so the row is retried on a later run.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, ListingGone, SearchQuery, parse_posted_at, stable_id

log = structlog.get_logger()

_BASE = "https://wellfound.com"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"}
_MAX_AGE = timedelta(days=30)
_SLEEP_S = 1.5
_EN_DASH, _EM_DASH = chr(0x2013), chr(0x2014)
_JOB_HREF_RE = re.compile(r'href="/jobs/(\d+)-([^"?#/]+)"')
# "Posted: today", "Posted:3 days ago", "Posted: 3 years ago"
_POSTED_RE = re.compile(
    r"Posted:\s*(today|yesterday|(\d+)\s*(day|week|month|year)s?\s*ago)", re.IGNORECASE)
_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}
_REMOTE_RE = re.compile(r"Remote\s*\(\s*([^)]+?)\s*\)")
# The header's "$158k to $200k" shape, en-dash or hyphen, optional currency code.
_SALARY_RE = re.compile(r"\$\d[\d,.]*k\s*[" + _EN_DASH + r"-]\s*\$\d[\d,.]*k(?:\s*[A-Z]{3})?")


def _get(url: str) -> httpx.Response | None:
    """One polite GET. None when the request fails or Cloudflare blocks it;
    any other status comes back for the caller to judge."""
    time.sleep(_SLEEP_S)
    try:
        r = httpx.get(url, headers=_HEADERS, timeout=20.0, follow_redirects=True)
    except Exception as exc:
        log.warning("wellfound_fetch_failed", url=url, error=str(exc))
        return None
    if r.status_code == 403 or "just a moment" in r.text[:4000].lower():
        log.warning("wellfound_fetch_failed", url=url, status=r.status_code,
                    error="blocked by cloudflare")
        return None
    return r


def _clean_salary(s) -> str:
    return " ".join(str(s or "").replace(_EN_DASH, "-").replace(_EM_DASH, "-").split())


def _epoch(v) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _entries_from_next_data(html: str) -> list[dict]:
    node = HTMLParser(html).css_first("script#__NEXT_DATA__")
    if node is None:
        return []
    data = json.loads(node.text())
    cache = data.get("props", {}).get("pageProps", {}).get("apolloState", {}).get("data")
    if not isinstance(cache, dict):
        return []
    company_of: dict[str, str] = {}
    for key, val in cache.items():
        if key.startswith("StartupResult:") and isinstance(val, dict):
            for ref in val.get("highlightedJobListings") or []:
                if isinstance(ref, dict) and ref.get("__ref"):
                    company_of[ref["__ref"]] = val.get("name") or ""
    return [{**val, "company": company_of.get(key, "")}
            for key, val in cache.items()
            if key.startswith("JobListingSearchResult:") and isinstance(val, dict)]


def _entries_from_anchors(html: str) -> list[dict]:
    """Fallback without the JSON: id and slug from the card links, title from the slug."""
    pairs = dict.fromkeys(_JOB_HREF_RE.findall(html))
    return [{"id": i, "slug": s, "title": s.replace("-", " ").title()} for i, s in pairs]


def _jobposting_ld(tree: HTMLParser) -> dict:
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text())
        except (ValueError, TypeError):
            continue
        for item in (data if isinstance(data, list) else [data]):
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return {}


def _posted_from_text(text: str, now: datetime) -> datetime | None:
    """"Posted: N days ago" from the header. parse_posted_at has no "year"
    unit, so the arithmetic lives here; months and years are past the
    30-day cutoff by definition."""
    m = _POSTED_RE.search(text)
    if not m:
        return None
    if m.group(2) is None:
        return now - timedelta(days=int(m.group(1).lower() == "yesterday"))
    return now - timedelta(days=_DAYS[m.group(3).lower()] * int(m.group(2)))


def _location(ld: dict, text: str) -> str | None:
    m = _REMOTE_RE.search(text)
    if m:
        return f"Remote ({m.group(1)})"
    places = ld.get("jobLocation")
    for place in (places if isinstance(places, list) else [places]):
        addr = place.get("address") if isinstance(place, dict) else None
        keys = ("addressLocality", "addressRegion", "addressCountry")
        parts = [addr.get(k) for k in keys if addr.get(k)] if isinstance(addr, dict) else []
        if parts:
            return ", ".join(parts)
    return "Remote" if ld.get("jobLocationType") == "TELECOMMUTE" else None


def _salary(ld: dict, text: str) -> str:
    """The header's own string first, the JSON-LD baseSalary as fallback."""
    m = _SALARY_RE.search(text)
    if m:
        return _clean_salary(m.group(0))
    base = ld.get("baseSalary") if isinstance(ld.get("baseSalary"), dict) else {}
    val = base.get("value") if isinstance(base.get("value"), dict) else {}
    parts = [f"${int(x) // 1000}k" for x in (val.get("minValue"), val.get("maxValue"))
             if isinstance(x, (int, float)) and x]
    cur = base.get("currency") or "USD"
    return " - ".join(dict.fromkeys(parts)) + (f" {cur}" if parts and cur != "USD" else "")


class WellfoundScraper(BaseScraper):
    source = "wellfound"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """query example: {"q": "product manager"}. The role slug is the query
        with hyphens, so "product owner" reads /role/r/product-owner."""
        needle = " ".join((query.get("q") or "product manager").lower().split())
        url = f"{_BASE}/role/r/{needle.replace(' ', '-')}"
        r = _get(url)
        if r is None:
            return []
        if r.status_code != 200:
            log.warning("wellfound_fetch_failed", url=url, status=r.status_code)
            return []
        try:
            entries = _entries_from_next_data(r.text)
        except Exception as exc:
            log.warning("wellfound_parse_failed", url=url, error=str(exc))
            entries = []
        entries = entries or _entries_from_anchors(r.text)

        cutoff = datetime.now(timezone.utc) - _MAX_AGE
        out: list[JobPosting] = []
        n_stale = 0
        for e in entries:
            title = " ".join(str(e.get("title") or "").split())
            if not e.get("id") or not e.get("slug") or needle not in title.lower():
                continue
            posted_at = _epoch(e.get("liveStartAt"))
            if posted_at is not None and posted_at <= cutoff:
                n_stale += 1
                continue
            job_url = f"{_BASE}/jobs/{e['id']}-{e['slug']}"
            salary = _clean_salary(e.get("compensation"))
            locations = [x for x in (e.get("locationNames") or []) if isinstance(x, str)]
            out.append(JobPosting(
                id=stable_id(self.source, job_url),
                source=self.source,
                title=title,
                company=(e.get("company") or "Unknown").strip(),
                location=", ".join(locations) if locations else "Remote",
                url=job_url,
                apply_url=job_url,
                posted_at=posted_at,
                description=str(e.get("description") or "")[:12000],
                tags=["remote", "startup"] + ([f"salary: {salary}"] if salary else []),
            ))
        log.info("wellfound_fetched", n=len(out), stale_skipped=n_stale, q=needle)
        return out

    def fetch_detail(self, job: JobPosting) -> JobPosting | None:
        """Read the public detail page. 404 or 410, a redirect off /jobs/, or a
        posting older than 30 days (see the module docstring) raises
        ListingGone. 403, a Cloudflare page or a short body returns None so
        the runner retries on a later run."""
        url = str(job.url)
        r = _get(url)
        if r is None:
            return None
        if r.status_code in (404, 410):
            raise ListingGone(f"wellfound returned HTTP {r.status_code}")
        if r.status_code != 200:
            log.warning("wellfound_detail_failed", url=url, status=r.status_code)
            return None
        if "/jobs/" not in str(r.url):
            raise ListingGone(f"redirected to {str(r.url)[:120]}")

        tree = HTMLParser(r.text)
        ld = _jobposting_ld(tree)
        body_text = tree.body.text(separator=" ", strip=True) if tree.body else ""
        now = datetime.now(timezone.utc)
        posted_at = parse_posted_at(ld.get("datePosted")) or _posted_from_text(body_text, now)
        if posted_at is not None and posted_at <= now - _MAX_AGE:
            raise ListingGone("posted more than 30 days ago")

        description = HTMLParser(ld.get("description") or "").text(separator="\n", strip=True)
        if len(description.split()) < 100:
            return None
        update: dict = {"description": description[:12000],
                        "posted_at": posted_at or job.posted_at}
        org = ld.get("hiringOrganization")
        if isinstance(org, dict) and str(org.get("name") or "").strip():
            update["company"] = str(org["name"]).strip()
        location = _location(ld, body_text)
        if location:
            update["location"] = location
        salary = _salary(ld, body_text)
        kept = [t for t in job.tags if t not in ("remote", "startup") and not t.startswith("salary:")]
        update["tags"] = ["remote", "startup"] + kept + ([f"salary: {salary}"] if salary else [])
        return job.model_copy(update=update)
