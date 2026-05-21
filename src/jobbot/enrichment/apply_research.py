"""Apply-path research: resolve a canonical employer apply URL for a
posting whose only known link is a paywalled aggregator (dailyremote,
LinkedIn, Xing) where the real application form is gated.

The aggregator detail pages do not expose the canonical URL (verified:
dailyremote's JSON-LD `url` is the aggregator link, no outbound ATS
links, apply button is premium-gated JS). The only way to recover it is
to search the web for "<company> <title> careers/apply" and identify the
employer's real ATS (Greenhouse / Lever / TeamTailor / Personio / Ashby
/ Workable / SmartRecruiters / company careers page).

We use the Anthropic server-side `web_search` tool so this works
headless in the scheduled pipeline (no agent tools, no extra search-API
key). One model call per researched row; cost is bounded by the
enrichment runner's per-run cap and by skipping rows that already have a
usable non-paywalled route.
"""
from __future__ import annotations

import json
import re

import structlog

log = structlog.get_logger()

_MODEL = "claude-sonnet-4-6"

_SYSTEM = """You find the canonical employer application URL for a job
posting. The link we have is a paywalled job-board aggregator; we need
the real place a candidate applies: the employer's ATS posting
(Greenhouse, Lever, TeamTailor, Personio, Ashby, Workable,
SmartRecruiters, Recruitee, join.com) or the company's own careers page
for this exact role.

Rules:
- Search the web, then return ONLY a JSON object, no prose, no fences.
- Schema: {"apply_url": <string|null>, "ats": <string|null>,
  "confidence": "high"|"medium"|"low", "reason": <short string>}.
- apply_url must be a direct posting for THIS role at THIS company when
  possible; a company careers/jobs index is acceptable only if the exact
  posting can't be found. Never return the aggregator URL back.
- If you cannot find a credible employer URL, return apply_url: null with
  a short reason. Do not guess or fabricate a URL.
- Never use em-dashes in any string value."""


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    # Find the first {...} block if the model wrapped it in stray prose.
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def research_apply_url(
    company: str,
    title: str,
    current_url: str | None,
    secrets,
    *,
    max_searches: int = 4,
) -> tuple[str | None, str]:
    """Return (canonical_apply_url, note). url is None when nothing
    credible was found. `note` carries the ATS name + confidence or the
    failure reason, for logging / the dashboard."""
    if not company or not title:
        return None, "missing company or title"
    try:
        from anthropic import Anthropic
    except ImportError:
        return None, "anthropic SDK not installed"

    client = Anthropic(api_key=secrets.anthropic_api_key)
    prompt = (
        f"Company: {company}\n"
        f"Role title: {title}\n"
        f"Aggregator link we have (do NOT return this): {current_url or 'n/a'}\n\n"
        f"Find where a candidate actually applies for this exact role."
    )
    try:
        msg = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=_SYSTEM,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_searches,
            }],
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        log.warning("apply_research_failed", company=company, error=str(e))
        return None, f"web_search error: {type(e).__name__}"

    # The final assistant text block carries the JSON answer.
    text = "".join(
        b.text for b in msg.content if getattr(b, "type", None) == "text"
    )
    parsed = _extract_json(text)
    if not parsed:
        return None, "no parseable JSON in research result"
    url = parsed.get("apply_url")
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return None, parsed.get("reason") or "no apply_url found"
    note = f"{parsed.get('ats') or 'unknown ATS'} ({parsed.get('confidence') or '?'})"
    return url, note
