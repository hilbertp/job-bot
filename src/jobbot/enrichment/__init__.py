"""enrichment — between scrape and score, fetch the full posting body and
extract structured signals (seniority, salary, apply email).

PRD §7.3 (Enrichment).

The pipeline calls `enrich_new_postings(jobs, conn)` after the scrape phase.
For each posting:
  1. Look up the source's scraper. If it has `fetch_detail()`, call it.
  2. If the returned body is ≥ 100 words, store it in `seen_jobs.description_full`,
     set `description_scraped = True`, compute word count.
  3. Run regex / LLM extraction over the body to populate:
       seniority, salary_text, apply_email
  4. If body fetch failed, keep `description_scraped = False` and the
     posting will not be scored.

Per-source rate limits apply (each scraper handles its own throttle).
Failure of one detail-fetch does not abort the rest.
"""
from .runner import enrich_new_postings  # noqa: F401
from .email_extractor import extract_apply_email  # noqa: F401
