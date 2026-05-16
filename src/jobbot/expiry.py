"""Shared listing-expiry detection.

Two callers:
  - `applier.runner.apply_to_job` pre-flights `apply_url` before launching
    Chromium so it can skip cleanly when a role was pulled between scoring
    and apply.
  - `housekeep.housekeep_shortlist` runs the same probe across every live
    shortlist row periodically so stale postings get marked LISTING_EXPIRED
    without waiting for an apply attempt.

Both use `is_expired_listing(final_url, status)`. Keeping the rule in one
file means the two probes stay in lockstep.
"""
from __future__ import annotations


# URL-path needles that signal a posting was pulled. When the apply_url
# redirects to one of these (or directly matches), the role no longer
# accepts applications. Consensys's Greenhouse `jobs/{id}` page redirects
# to `consensys.io/open-roles` once a role closes; the same shape recurs
# with `/careers`, `/jobs/search`, `/positions`, generic 404 pages, etc.
EXPIRED_URL_PATTERNS = (
    "/open-roles",
    "/openings",
    "/careers/index",
    "/jobs/search",
    "/jobs/all",
    "/job-search",
    "/job-not-found",
    "/job_expired",
    "expired",
    "no-longer-available",
    "404",
)


def is_expired_listing(final_url: str, response_status: int) -> tuple[bool, str]:
    """Return (is_expired, reason) for a listing whose apply_url no longer
    resolves to an application form. Two signals:

      1. HTTP 403 / 404 / 410 on the apply_url (the job was deleted).
      2. The URL after redirects lands on a known "generic" path
         (e.g. /open-roles, /careers/index, /jobs/search), meaning the
         specific posting redirected to the company's hiring index.

    Both signals are strong; if either fires the caller should treat the
    row as LISTING_EXPIRED.
    """
    if response_status in (403, 404, 410):
        return True, f"HTTP {response_status} from apply_url"
    if final_url:
        lower = final_url.lower()
        for needle in EXPIRED_URL_PATTERNS:
            if needle in lower:
                # Avoid false positives on /jobs/{id} URLs that legitimately
                # contain the substring 'jobs', we require a generic
                # PATH segment, not a numeric job-id suffix.
                if needle == "404" and "/404" not in lower:
                    continue
                return True, f"apply_url redirected to a generic page ({final_url})"
    return False, ""
