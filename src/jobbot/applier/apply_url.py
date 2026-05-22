"""Apply-URL normalization.

Some ATSes serve a job DESCRIPTION page at the posting URL and keep the
actual application FORM on a sub-path. If the runner navigates to the JD
page, the LLM-fill adapter finds no form (or the wrong one) and the apply
stalls. Ashby is the recurring case: the posting lives at

    https://jobs.ashbyhq.com/<org>/<uuid>

but the form is at

    https://jobs.ashbyhq.com/<org>/<uuid>/application

Normalizing the URL to the form path before navigation makes Ashby applies
land directly on the fillable form (observed 2026-05-21: Sweed and Nylas
both fell back to the dry-run GenericAdapter on their JD pages until the
URL was pointed at /application).
"""
from __future__ import annotations

import re

# jobs.ashbyhq.com/<org-slug>/<36-char-uuid>  (no trailing /application).
# Captures up to the uuid so we can append the form path. Query strings and
# trailing slashes are stripped from the matched portion.
_ASHBY_JOB_RE = re.compile(
    r"^(https?://jobs\.ashbyhq\.com/[^/]+/[0-9a-fA-F-]{36})/?$"
)


def normalize_apply_url(url: str | None) -> str | None:
    """Return the form URL for known JD-page ATSes, else the URL unchanged.

    Currently handles Ashby: a bare `/<org>/<uuid>` posting URL is rewritten
    to `/<org>/<uuid>/application`. URLs that already point at `/application`
    (or any other path shape) are returned untouched. None/empty pass through.
    """
    if not url:
        return url
    base = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    m = _ASHBY_JOB_RE.match(base)
    if m:
        return m.group(1) + "/application"
    return url
