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


# Visible-text needles that signal a posting was pulled even though the URL
# still resolves HTTP 200 with no redirect. Some ATSes keep the posting URL
# alive after a role closes and serve a banner instead of a form, so the
# URL/status checks in `is_expired_listing` miss them. SmartRecruiters did
# exactly this on the Accesa posting (2026-05-21): "Sorry, this job has
# expired." on a 200 page. Match is case-insensitive substring against the
# page's visible body text. Phrases are kept tight + job-expiry-specific so
# they don't false-positive on a live form's body copy.
EXPIRED_TEXT_PATTERNS = (
    # English
    "this job has expired",
    "this job posting has expired",
    "this posting has expired",
    "this position has expired",
    "this job is no longer available",
    "this position is no longer available",
    "this job is no longer active",
    "this opportunity is no longer available",
    "no longer accepting applications",
    "we are no longer accepting applications",
    "this job has been filled",
    "this position has been filled",
    "the position has been filled",
    "applications are now closed",
    "application period has ended",
    "job posting is no longer available",
    # German
    "stelle ist nicht mehr verfügbar",
    "stelle ist leider nicht mehr verfügbar",
    "position ist nicht mehr verfügbar",
    "stellenanzeige ist nicht mehr verfügbar",
    "stellenanzeige ist nicht mehr aktiv",
    "anzeige ist nicht mehr verfügbar",
    "bewerbungsfrist ist abgelaufen",
    "bewerbungsfrist abgelaufen",
    "stelle ist bereits besetzt",
    "stelle bereits vergeben",
    "diese position ist bereits besetzt",
)


def is_expired_by_text(body_text: str) -> tuple[bool, str]:
    """Return (is_expired, reason) for a page that loaded HTTP 200 with no
    redirect but shows an inline "this job has expired / no longer available
    / has been filled" banner instead of an application form.

    Complements `is_expired_listing` (which only sees URL + status): callers
    that have the rendered page text (the apply runner has it cheaply via the
    live Playwright page) scan it here to catch 200-with-banner listings.
    Match is case-insensitive substring against the visible body text.
    """
    if not body_text:
        return False, ""
    lower = body_text.lower()
    for needle in EXPIRED_TEXT_PATTERNS:
        if needle in lower:
            return True, f"page shows expiry banner ({needle!r})"
    return False, ""


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
