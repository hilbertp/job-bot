"""Local read-only dashboard at http://localhost:5001.

PRD §7.10.

Renders the same data as the daily digest plus the long tail of postings
truncated from the email. Read-only, v1 has no state-mutation endpoints.
Backed by FastAPI (or Flask, Copilot's pick) reading directly from
`data/jobbot.db`.

Routes:
  GET /, funnel snapshot, today's matches, applications
  GET /postings, paginated table of every posting in the DB
  GET /postings/<id>, detail view of one posting (full body, breakdown, output dir)
  GET /applications, table of every application with current proof level
  GET /sources, per-source health stats (last 7 days)

No auth (binds to localhost only).
"""
from .server import run  # noqa: F401
