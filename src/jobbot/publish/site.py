"""Build a self-contained static dashboard from the SQLite state.

The output is a plain directory (index.html + data.json + docs/ PDFs +
.nojekyll) that any static host can serve; `jobbot publish` points it at a
GitHub Pages repo. No server-side code, no external assets.
"""
from __future__ import annotations

import html
import json
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from ..config import REPO_ROOT, Config
from ..state import usable_apply_route

log = structlog.get_logger()

# PDF artifacts produced by generators.pipeline for each generated job.
DOC_FILENAMES = ("cv.pdf", "cover_letter.pdf", "application_package.pdf")


@dataclass
class SiteBuildReport:
    n_jobs: int = 0
    n_docs_copied: int = 0
    generated_at: str = ""
    site_dir: str = ""
    warnings: list[str] = field(default_factory=list)


def _raw_payload(row: sqlite3.Row) -> dict:
    try:
        payload = json.loads(row["raw_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        payload = {}
    return payload if isinstance(payload, dict) else {}


def resolve_output_dir(output_dir: str | None, repo_root: Path) -> Path | None:
    """seen_jobs.output_dir may be absolute or relative to the repo root."""
    if not output_dir:
        return None
    p = Path(output_dir)
    if not p.is_absolute():
        p = repo_root / p
    return p if p.is_dir() else None


def _job_documents(row: sqlite3.Row, repo_root: Path) -> list[str]:
    out_dir = resolve_output_dir(row["output_dir"], repo_root)
    if out_dir is None:
        return []
    return [name for name in DOC_FILENAMES if (out_dir / name).is_file()]


def collect_site_jobs(
    conn: sqlite3.Connection,
    config: Config,
    *,
    repo_root: Path = REPO_ROOT,
    now: datetime | None = None,
) -> list[dict]:
    """Rows worth showing: scored at/above the floor and recent, best first."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=config.publish.max_age_days)).isoformat()
    rows = conn.execute(
        "SELECT * FROM seen_jobs"
        " WHERE score IS NOT NULL AND score >= ? AND first_seen_at >= ?"
        " ORDER BY COALESCE(score_tailored, score) DESC, first_seen_at DESC"
        " LIMIT ?",
        (config.publish.min_score, cutoff, config.publish.max_jobs),
    ).fetchall()

    today = now.date().isoformat()
    jobs: list[dict] = []
    for row in rows:
        payload = _raw_payload(row)
        if config.publish.posted_today_only:
            stamp = str(payload.get("posted_at") or row["first_seen_at"] or "")[:10]
            if stamp != today:
                continue
        apply_url = payload.get("apply_url") or row["url"]
        route, target = usable_apply_route(row["apply_email"], apply_url)
        jobs.append({
            "id": row["id"],
            "source": row["source"],
            "title": row["title"] or "",
            "company": row["company"] or "",
            "location": row["location"] if "location" in row.keys() else payload.get("location"),
            "salary": row["salary_text"],
            "score": row["score"],
            "score_tailored": row["score_tailored"],
            "status": row["status"],
            "first_seen_at": row["first_seen_at"],
            "posted_at": payload.get("posted_at"),
            "apply_route": route,
            "apply_target": target if route in ("url", "email") else None,
            "documents": _job_documents(row, repo_root),
        })
    return jobs


def collect_recent_runs(conn: sqlite3.Connection, limit: int = 14) -> list[dict]:
    rows = conn.execute(
        "SELECT id, started_at, finished_at, n_fetched, n_new, n_generated,"
        " n_applied, n_errors FROM runs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def copy_documents(jobs: list[dict], conn: sqlite3.Connection, site_dir: Path,
                   *, repo_root: Path = REPO_ROOT) -> int:
    """Mirror each shown job's PDFs into site_dir/docs/<job_id>/.

    The docs tree is rebuilt from scratch on every publish so jobs that
    dropped off the dashboard don't leave stale files on the site.
    """
    docs_root = site_dir / "docs"
    if docs_root.exists():
        shutil.rmtree(docs_root)
    copied = 0
    for job in jobs:
        if not job["documents"]:
            continue
        row = conn.execute(
            "SELECT output_dir FROM seen_jobs WHERE id = ?", (job["id"],)
        ).fetchone()
        out_dir = resolve_output_dir(row["output_dir"] if row else None, repo_root)
        if out_dir is None:
            continue
        target = docs_root / job["id"]
        target.mkdir(parents=True, exist_ok=True)
        for name in job["documents"]:
            shutil.copyfile(out_dir / name, target / name)
            copied += 1
    return copied


def build_site(
    conn: sqlite3.Connection,
    config: Config,
    site_dir: Path,
    *,
    repo_root: Path = REPO_ROOT,
    now: datetime | None = None,
) -> SiteBuildReport:
    """Write index.html + data.json (+ docs/) into site_dir."""
    now = now or datetime.now(timezone.utc)
    report = SiteBuildReport(generated_at=now.isoformat(), site_dir=str(site_dir))
    site_dir.mkdir(parents=True, exist_ok=True)

    jobs = collect_site_jobs(conn, config, repo_root=repo_root, now=now)
    runs = collect_recent_runs(conn)
    report.n_jobs = len(jobs)

    if config.publish.include_documents:
        report.n_docs_copied = copy_documents(jobs, conn, site_dir, repo_root=repo_root)
    else:
        for job in jobs:
            job["documents"] = []

    data = {"generated_at": report.generated_at, "jobs": jobs, "runs": runs}
    (site_dir / "data.json").write_text(json.dumps(data, indent=2, default=str))
    (site_dir / "index.html").write_text(render_index_html(config, jobs, runs, now))
    # Tell GitHub Pages to serve the tree verbatim, no Jekyll pass.
    (site_dir / ".nojekyll").write_text("")
    log.info("site_built", dir=str(site_dir), jobs=len(jobs), docs=report.n_docs_copied)
    return report


# --------------------------------------------------------------------------
# HTML rendering. Kept as an inline template so the package needs no
# package-data configuration; the page is fully self-contained.
# --------------------------------------------------------------------------

_DOC_LABELS = {
    "cv.pdf": "CV",
    "cover_letter.pdf": "Cover letter",
    "application_package.pdf": "Full package",
}

_PAGE_CSS = """
:root {
  --bg: #0f1115; --panel: #171a21; --panel2: #1d212b; --text: #e8eaf0;
  --muted: #9aa3b5; --line: #2a2f3c; --accent: #7aa2ff; --good: #3fb96f;
  --mid: #d7a63f; --link: #8ab4ff;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #f6f7f9; --panel: #ffffff; --panel2: #eef1f6; --text: #1a202c;
    --muted: #5b6472; --line: #dde2ea; --accent: #2f5fd0; --good: #1e8a4c;
    --mid: #9a7413; --link: #2456b8;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width: 1280px; margin: 0 auto; padding: 24px 20px 60px; }
h1 { font-size: 22px; margin: 0; letter-spacing: 0.2px; }
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
.header { display: flex; flex-wrap: wrap; gap: 12px; align-items: baseline;
  justify-content: space-between; margin-bottom: 18px; }
.meta { color: var(--muted); font-size: 13px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; margin-bottom: 20px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: 14px 16px; }
.card .num { font-size: 26px; font-weight: 650; }
.card .lbl { color: var(--muted); font-size: 12px; text-transform: uppercase;
  letter-spacing: 0.8px; }
.controls { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px;
  align-items: center; }
.controls input[type=search] { flex: 1 1 240px; max-width: 380px; padding: 8px 12px;
  border-radius: 8px; border: 1px solid var(--line); background: var(--panel);
  color: var(--text); font-size: 14px; }
.controls label { color: var(--muted); font-size: 13px; }
.tablewrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 10px;
  background: var(--panel); }
table { border-collapse: collapse; width: 100%; min-width: 980px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line);
  vertical-align: top; }
th { font-size: 12px; text-transform: uppercase; letter-spacing: 0.7px;
  color: var(--muted); cursor: pointer; user-select: none; white-space: nowrap;
  background: var(--panel2); position: sticky; top: 0; }
th .grip { position: absolute; top: 0; right: 0; width: 8px; height: 100%;
  cursor: col-resize; }
th .grip:hover, th .grip.active { background: var(--accent); opacity: 0.45; }
table.resized { table-layout: fixed; }
table.resized td { overflow: hidden; text-overflow: ellipsis; }
tr:last-child td { border-bottom: none; }
.badge { display: inline-block; min-width: 38px; text-align: center; padding: 2px 8px;
  border-radius: 999px; font-weight: 650; font-size: 13px; }
.badge.hi { background: rgba(63,185,111,.15); color: var(--good); }
.badge.mid { background: rgba(215,166,63,.15); color: var(--mid); }
.badge.na { color: var(--muted); font-weight: 400; }
.newpill { display: inline-block; margin-left: 6px; padding: 1px 7px; font-size: 11px;
  border-radius: 999px; background: rgba(122,162,255,.18); color: var(--accent);
  font-weight: 650; vertical-align: middle; }
.src { color: var(--muted); font-size: 12px; }
.docs a { display: inline-block; margin-right: 8px; white-space: nowrap; }
.apply { white-space: nowrap; font-weight: 550; }
.noroute { color: var(--muted); font-size: 13px; }
.runs { margin-top: 26px; }
.runs h2 { font-size: 15px; color: var(--muted); text-transform: uppercase;
  letter-spacing: 0.8px; }
.runs table { min-width: 640px; }
footer { margin-top: 28px; color: var(--muted); font-size: 12px; }
"""

_PAGE_JS = """
(function () {
  const q = document.getElementById('q');
  const minScore = document.getElementById('minscore');
  const minLabel = document.getElementById('minscore-label');
  const rows = Array.from(document.querySelectorAll('tbody#jobs tr'));
  function apply() {
    const needle = (q.value || '').toLowerCase();
    const floor = parseInt(minScore.value, 10) || 0;
    minLabel.textContent = floor;
    let shown = 0;
    rows.forEach(function (tr) {
      const hay = tr.getAttribute('data-hay');
      const best = parseInt(tr.getAttribute('data-best'), 10) || 0;
      const ok = (!needle || hay.indexOf(needle) !== -1) && best >= floor;
      tr.style.display = ok ? '' : 'none';
      if (ok) shown += 1;
    });
    document.getElementById('shown-count').textContent = shown;
  }
  q.addEventListener('input', apply);
  minScore.addEventListener('input', apply);
  let sortState = {};
  document.querySelectorAll('th[data-sort]').forEach(function (th) {
    th.addEventListener('click', function () {
      const key = th.getAttribute('data-sort');
      const numeric = th.getAttribute('data-num') === '1';
      sortState[key] = !sortState[key];
      const dir = sortState[key] ? 1 : -1;
      const tbody = document.getElementById('jobs');
      rows.sort(function (a, b) {
        let av = a.getAttribute('data-' + key) || '';
        let bv = b.getAttribute('data-' + key) || '';
        if (numeric) { av = parseFloat(av) || 0; bv = parseFloat(bv) || 0; }
        return av < bv ? -dir : av > bv ? dir : 0;
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    });
  });
  // Resizable columns: drag the right edge of any header cell.
  document.querySelectorAll('th').forEach(function (th) {
    const grip = document.createElement('div');
    grip.className = 'grip';
    th.appendChild(grip);
    grip.addEventListener('click', function (e) { e.stopPropagation(); });
    grip.addEventListener('mousedown', function (e) {
      e.preventDefault();
      e.stopPropagation();
      const table = th.closest('table');
      const startX = e.pageX;
      const startW = th.offsetWidth;
      // Freeze current widths once, so dragging one column does not
      // reflow the others.
      if (!table.classList.contains('resized')) {
        table.querySelectorAll('thead th').forEach(function (h) {
          h.style.width = h.offsetWidth + 'px';
        });
        table.classList.add('resized');
      }
      grip.classList.add('active');
      function move(ev) {
        th.style.width = Math.max(48, startW + ev.pageX - startX) + 'px';
      }
      function up() {
        grip.classList.remove('active');
        document.removeEventListener('mousemove', move);
        document.removeEventListener('mouseup', up);
      }
      document.addEventListener('mousemove', move);
      document.addEventListener('mouseup', up);
    });
  });
  apply();
})();
"""


def _score_badge(score: int | None) -> str:
    if score is None:
        return '<span class="badge na">n/a</span>'
    cls = "hi" if score >= 80 else "mid"
    return f'<span class="badge {cls}">{score}</span>'


def _fmt_ts(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value[:16]


def _job_row_html(job: dict, now: datetime) -> str:
    e = html.escape
    best = job["score_tailored"] or job["score"] or 0
    first_seen = job["first_seen_at"] or ""
    is_new = False
    try:
        seen_dt = datetime.fromisoformat(first_seen)
        if seen_dt.tzinfo is None:
            seen_dt = seen_dt.replace(tzinfo=timezone.utc)
        is_new = (now - seen_dt) <= timedelta(hours=26)
    except ValueError:
        pass
    newpill = '<span class="newpill">NEW</span>' if is_new else ""

    if job["apply_route"] == "url":
        apply_cell = (f'<a class="apply" href="{e(job["apply_target"])}"'
                      f' target="_blank" rel="noopener">Apply</a>')
    elif job["apply_route"] == "email":
        apply_cell = (f'<a class="apply" href="mailto:{e(job["apply_target"])}">'
                      f'{e(job["apply_target"])}</a>')
    else:
        # Never show a paywalled aggregator link as an apply route.
        apply_cell = '<span class="noroute">no direct route yet</span>'

    if job["documents"]:
        doc_links = " ".join(
            f'<a href="docs/{e(job["id"])}/{name}" download>{_DOC_LABELS[name]}</a>'
            for name in job["documents"]
        )
        docs_cell = f'<span class="docs">{doc_links}</span>'
    else:
        docs_cell = '<span class="noroute">not generated</span>'

    hay = e(" ".join(str(v or "") for v in
                     (job["title"], job["company"], job["location"],
                      job["source"], job["salary"])).lower())
    return (
        f'<tr data-hay="{hay}" data-best="{best}" data-score="{job["score"] or 0}"'
        f' data-tailored="{job["score_tailored"] or 0}"'
        f' data-company="{e((job["company"] or "").lower())}"'
        f' data-seen="{e(first_seen)}">'
        f'<td>{e(job["company"])}<div class="src">{e(job["source"])}</div></td>'
        f'<td>{e(job["title"])}{newpill}</td>'
        f'<td>{e(job["location"] or "")}</td>'
        f'<td>{e(job["salary"] or "")}</td>'
        f'<td>{_score_badge(job["score"])}</td>'
        f'<td>{_score_badge(job["score_tailored"])}</td>'
        f'<td>{apply_cell}</td>'
        f'<td>{docs_cell}</td>'
        f'<td class="meta">{_fmt_ts(first_seen)}</td>'
        f'</tr>'
    )


def render_index_html(config: Config, jobs: list[dict], runs: list[dict],
                      now: datetime) -> str:
    e = html.escape
    latest = runs[0] if runs else None
    new_today = sum(
        1 for j in jobs
        if (j["first_seen_at"] or "")[:10] == now.date().isoformat()
    )
    with_docs = sum(1 for j in jobs if j["documents"])

    latest_line = "No runs recorded yet."
    if latest:
        latest_line = (
            f"Latest run {e(_fmt_ts(latest['started_at']))} UTC:"
            f" {latest['n_fetched']} fetched, {latest['n_new']} new,"
            f" {latest['n_generated']} packages generated"
        )
        if latest["n_errors"]:
            latest_line += f", {latest['n_errors']} errors"

    job_rows = "\n".join(_job_row_html(j, now) for j in jobs)
    run_rows = "\n".join(
        f"<tr><td>{r['id']}</td><td>{e(_fmt_ts(r['started_at']))}</td>"
        f"<td>{e(_fmt_ts(r['finished_at']))}</td><td>{r['n_fetched']}</td>"
        f"<td>{r['n_new']}</td><td>{r['n_generated']}</td>"
        f"<td>{r['n_errors']}</td></tr>"
        for r in runs
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{e(config.publish.site_title)}</title>
<style>{_PAGE_CSS}</style>
</head>
<body>
<main>
  <div class="header">
    <h1>{e(config.publish.site_title)}</h1>
    <span class="meta">Generated {e(_fmt_ts(now.isoformat()))} UTC</span>
  </div>
  <div class="cards">
    <div class="card"><div class="num">{len(jobs)}</div><div class="lbl">Matches shown</div></div>
    <div class="card"><div class="num">{new_today}</div><div class="lbl">New today</div></div>
    <div class="card"><div class="num">{with_docs}</div><div class="lbl">Ready-to-send packages</div></div>
    <div class="card"><div class="num" id="shown-count">{len(jobs)}</div><div class="lbl">After filters</div></div>
  </div>
  <p class="meta">{latest_line}</p>
  <div class="controls">
    <input id="q" type="search" placeholder="Filter by company, title, location, source">
    <label>Min score <input id="minscore" type="range" min="0" max="100"
      value="{config.publish.min_score}" step="5">
      <b id="minscore-label">{config.publish.min_score}</b></label>
  </div>
  <div class="tablewrap">
  <table>
    <thead><tr>
      <th data-sort="company">Company</th>
      <th>Title</th>
      <th>Location</th>
      <th>Salary</th>
      <th data-sort="score" data-num="1">Base score</th>
      <th data-sort="tailored" data-num="1">Tailored score</th>
      <th>Apply</th>
      <th>Documents</th>
      <th data-sort="seen">First seen</th>
    </tr></thead>
    <tbody id="jobs">
{job_rows}
    </tbody>
  </table>
  </div>
  <div class="runs">
    <h2>Recent runs</h2>
    <div class="tablewrap">
    <table>
      <thead><tr><th>Run</th><th>Started</th><th>Finished</th><th>Fetched</th>
        <th>New</th><th>Generated</th><th>Errors</th></tr></thead>
      <tbody>
{run_rows}
      </tbody>
    </table>
    </div>
  </div>
  <footer>Built by jobbot. Data also available as <a href="data.json">data.json</a>.</footer>
</main>
<script>{_PAGE_JS}</script>
</body>
</html>
"""
