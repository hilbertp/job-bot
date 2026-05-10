"""Extract a contact email from a job-posting body.

PRD §7.3 FR-ENR-04.

Heuristic: scan the body with `[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}`,
prefer addresses whose local-part is one of:
    careers, jobs, bewerbung, recruiting, recruiter, talent, hr, jobs-de
Return the first preferred match; otherwise the first plausible match;
otherwise None.

Filter out noise (reply-to noise, "linkedin.com" addresses, etc.).
"""
from __future__ import annotations

import re

PREFERRED_LOCAL_PARTS = {
    "careers", "career", "jobs", "bewerbung", "bewerbungen",
    "recruiting", "recruiter", "talent", "hr", "jobs-de", "join",
}
EMAIL_RE = re.compile(r"[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
DOMAIN_BLOCKLIST = {"linkedin.com", "indeed.com", "stepstone.de", "xing.com",
                    "noreply", "no-reply", "donotreply"}


def extract_apply_email(body: str) -> str | None:
    """Return the most likely application contact email from `body`, or None."""
    if not body:
        return None

    matches = EMAIL_RE.findall(body)
    if not matches:
        return None

    preferred: list[str] = []
    plausible: list[str] = []

    for raw in matches:
        email = raw.strip().strip(".,;:()[]{}<>'\"").lower()
        if "@" not in email:
            continue
        local, domain = email.split("@", 1)
        if not local or not domain:
            continue
        if any(token in email for token in DOMAIN_BLOCKLIST):
            continue
        if domain in DOMAIN_BLOCKLIST:
            continue

        plausible.append(email)
        if local in PREFERRED_LOCAL_PARTS:
            preferred.append(email)

    if preferred:
        return preferred[0]
    if plausible:
        return plausible[0]
    return None
