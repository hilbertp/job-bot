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
            "url": row["url"],
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
    # Built-but-unsent packages across the whole corpus, independent of the
    # table's age window, so shortening that window never silently hides an
    # outstanding to-do.
    unsent_all_time = conn.execute(
        "SELECT COUNT(*) FROM seen_jobs WHERE output_dir IS NOT NULL"
        " AND output_dir != '' AND status = 'generated'"
    ).fetchone()[0]
    (site_dir / "index.html").write_text(
        render_index_html(config, jobs, runs, now, unsent_all_time=unsent_all_time)
    )
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
.header .actions { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.meta { color: var(--muted); font-size: 13px; }
.btn { background: var(--accent); color: var(--bg); border: none; border-radius: 8px;
  padding: 8px 14px; font-weight: 650; font-size: 13px; cursor: pointer;
  font-family: inherit; }
.btn:hover { filter: brightness(1.12); }
.btn:disabled { opacity: 0.55; cursor: default; filter: none; }
/* Stop is destructive-adjacent, so it reads as a secondary action: outlined
   in the warning hue rather than a second filled button competing with
   "Run now". It only exists while a run is live. */
.btn-stop { background: transparent; color: var(--mid);
  border: 1px solid color-mix(in oklab, var(--mid) 60%, transparent); }
.btn-stop:hover { background: color-mix(in oklab, var(--mid) 12%, transparent);
  filter: none; }
.statbar { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 0;
  background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: 12px 16px; margin-bottom: 10px; }
.stat { display: inline-flex; align-items: baseline; gap: 7px; }
.stat .num { font-size: 17px; font-weight: 650; font-variant-numeric: tabular-nums; }
.stat .lbl { color: var(--muted); font-size: 13px; }
.statbar .sep { color: var(--line); margin: 0 14px; }
.runline { color: var(--muted); font-size: 13px; margin: 0 0 18px; }
.runline .err { color: var(--mid); font-weight: 550; }
.controls { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px;
  align-items: center; }
.controls input[type=search] { flex: 1 1 240px; max-width: 380px; padding: 8px 12px;
  border-radius: 8px; border: 1px solid var(--line); background: var(--panel);
  color: var(--text); font-size: 14px; }
.controls label { color: var(--muted); font-size: 13px; }
.controls select { padding: 7px 10px; border-radius: 8px; border: 1px solid var(--line);
  background: var(--panel); color: var(--text); font-size: 13px; }
.tablewrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 10px;
  background: var(--panel); }
table { border-collapse: collapse; width: 100%; min-width: 980px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line);
  vertical-align: top; }
th { font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--muted); user-select: none; white-space: nowrap;
  background: var(--panel2); position: sticky; top: 0; }
th[data-sort] { cursor: pointer; }
th[data-sort]:hover { color: var(--text); }
th .sort-ind { display: inline-block; width: 1em; color: var(--accent); }
tbody tr { transition: background-color 150ms cubic-bezier(0.25, 1, 0.5, 1); }
tbody tr:hover { background: var(--panel2); }
a:focus-visible, input:focus-visible, select:focus-visible,
th[data-sort]:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
input[type=range], select { accent-color: var(--accent); }
@media (prefers-reduced-motion: reduce) {
  tbody tr { transition: none; }
}
th .grip { position: absolute; top: 0; right: 0; width: 8px; height: 100%;
  cursor: col-resize; }
th .grip:hover, th .grip.active { background: var(--accent); opacity: 0.45; }
table.resized { table-layout: fixed; }
table.resized td { overflow: hidden; text-overflow: ellipsis; }
/* Row height is the scanning budget. A long title used to stack five lines
   and a comma-run location refused to wrap, so rows grew to ~140px and the
   table stopped being scannable. Clamp both to two lines; the full value is
   on the cell's title attribute and in data.json. */
/* Clamp the TEXT, never the cell: `display: -webkit-box` on a <td> stops it
   being a table cell, which collapses the column to one character per line.
   Learned the hard way on this table. */
.titlelink, .loctext, .cname { display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
/* A recruiter's legal name can run 60 characters ("Halian | Managed Services,
   Recruitment Agency & Contract Staffing"); clamped like everything else,
   full value on hover. */
/* Give the two text-heavy columns a sane share instead of letting content
   dictate it: without this, one 90-character location starves the title. */
th:nth-child(2), td:nth-child(2) { width: 26%; }
th:nth-child(3), td:nth-child(3) { width: 16%; }
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
.titlelink { color: inherit; text-decoration: underline;
  text-decoration-style: dotted; text-decoration-color: var(--muted);
  text-underline-offset: 3px; }
.titlelink:hover { color: var(--link); text-decoration-style: solid; }
.docs a { display: inline-block; margin-right: 8px; white-space: nowrap; }
.apply { white-space: nowrap; font-weight: 550; }
.noroute { color: var(--muted); font-size: 13px; }
/* An in-flight run is the single most time-sensitive thing on the page:
   it means the numbers below are mid-change. It therefore sits ABOVE the
   stat bar and carries an accent border, so it reads as an interruption
   rather than as one more panel. */
#active-run { background: var(--panel); border: 1px solid var(--good);
  border-left: 3px solid var(--good);
  border-radius: 10px; padding: 14px 16px; margin: 4px 0 18px; }
#active-run h2 { letter-spacing: 0.01em; }
/* The 80+ count is the number worth acting on; the rest is context. */
.stat.hot .num { color: var(--good); }
#active-run h2 { margin: 0; font-size: 14px; }
#ar-dot { display: inline-block; width: 9px; height: 9px; border-radius: 999px;
  margin-right: 7px; vertical-align: 1px; }
#ar-dot.running { background: var(--good);
  animation: ar-pulse 1.4s cubic-bezier(0.25, 1, 0.5, 1) infinite; }
#ar-dot.stalled { background: var(--mid); animation: none; }
#ar-dot.done { background: var(--good); animation: none; }
/* A run takes up to 90 minutes and the user switches to another tab while it
   works, so "in flight" has to be legible from the tab strip and from
   peripheral vision, not only when the panel is being read. Three layers:
   this viewport rail, the panel's live treatment below, and the tab title. */
#run-rail { position: fixed; inset: 0 0 auto 0; height: 3px; z-index: 60;
  background: color-mix(in oklab, var(--accent) 18%, transparent); }
#run-rail i { display: block; height: 100%; width: 0%; background: var(--accent);
  transition: width 400ms cubic-bezier(0.25, 1, 0.5, 1); }
/* A stage that has just started sits at 0%, which would render an invisible
   rail: the loudest signal would vanish exactly when a long stage begins.
   Slide a short segment instead, so "starting" still reads as "running". */
#run-rail.indeterminate i { width: 28%;
  animation: rail-travel 1.9s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
@keyframes rail-travel { from { transform: translateX(-100%); }
  to { transform: translateX(360%); } }
/* Live panel: distinct surface + border, so a running run never reads the
   same as a finished one. Full border, never a side stripe. */
#active-run.live { border-color: color-mix(in oklab, var(--accent) 55%, var(--line));
  background: color-mix(in oklab, var(--accent) 5%, var(--panel)); }
#active-run.live h2 { font-size: 15px; }
#active-run .runstate { font-weight: 650; color: var(--accent); }
#active-run.live #ar-elapsed { font-variant-numeric: tabular-nums; }
/* The count can sit still for minutes (7s per posting when scoring, longer
   when tailoring), so the active bar carries a moving sheen: it says "alive"
   exactly where the number cannot. */
.bar.working i { position: relative; overflow: hidden; }
.bar.working i::after { content: ""; position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent,
    color-mix(in oklab, var(--text) 45%, transparent), transparent);
  animation: bar-sheen 1.6s ease-in-out infinite; }
@keyframes bar-sheen { from { transform: translateX(-100%); }
  to { transform: translateX(200%); } }
@media (prefers-reduced-motion: reduce) {
  .bar.working i::after { animation: none;
    background: color-mix(in oklab, var(--text) 22%, transparent); }
  #run-rail i { transition: none; }
  /* Hold a visible sliver rather than sliding it. */
  #run-rail.indeterminate i { animation: none; width: 12%; }
}
#active-run .stalled-note { color: var(--mid); font-weight: 550; }
@keyframes ar-pulse {
  0% { box-shadow: 0 0 0 0 rgba(63, 185, 111, 0.45); }
  70% { box-shadow: 0 0 0 7px rgba(63, 185, 111, 0); }
  100% { box-shadow: 0 0 0 0 rgba(63, 185, 111, 0); }
}
@media (prefers-reduced-motion: reduce) {
  #ar-dot.running { animation: none; }
}
#active-run .arhead { display: flex; flex-wrap: wrap; gap: 6px 14px;
  align-items: baseline; }
.stagerow { display: flex; align-items: center; gap: 10px; margin-top: 8px;
  font-size: 13px; }
.stagerow .sname { flex: 0 0 110px; color: var(--muted); }
.bar { flex: 1; height: 6px; background: var(--panel2); border-radius: 999px;
  overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent);
  border-radius: 999px; transition: width 400ms cubic-bezier(0.25, 1, 0.5, 1); }
.stagerow .snum { flex: 0 0 auto; min-width: 90px; text-align: right;
  font-variant-numeric: tabular-nums; }
.stagerow .sfail { color: var(--mid); }
.funnelrow { margin: 3px 0 0 120px; font-size: 12px; color: var(--muted); }
#ar-strong { margin-top: 10px; font-size: 13px; font-weight: 600;
  color: var(--good); }
#ar-ticker { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
#ar-ticker .tick { display: inline-flex; align-items: baseline; gap: 5px;
  padding: 2px 9px; border-radius: 999px; font-size: 12px;
  background: var(--panel2); color: var(--muted);
  font-variant-numeric: tabular-nums; }
#ar-ticker .tick b { font-weight: 650; color: var(--text); }
#ar-ticker .tick.hit { background: rgba(63, 185, 111, 0.14); color: var(--good); }
#ar-ticker .tick.hit b { color: var(--good); }
#ar-fails { margin-top: 8px; font-size: 12.5px; color: var(--mid); }
#ar-stuck { margin-top: 10px; padding: 8px 11px; border-radius: 8px;
  font-size: 12.5px; font-weight: 550; color: var(--mid);
  background: rgba(191, 135, 0, 0.12); }
@media (prefers-reduced-motion: reduce) {
  .bar i { transition: none; }
}
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
  const timeWin = document.getElementById('timewin');
  const rows = Array.from(document.querySelectorAll('tbody#jobs tr[data-hay]'));
  function inWindow(tr) {
    const stamp = tr.getAttribute('data-posted');
    if (!stamp) return timeWin.value === '0';
    if (timeWin.value === 'yesterday') {
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - 1);
      const pad = function (n) { return String(n).padStart(2, '0'); };
      const ymd = cutoff.getFullYear() + '-' + pad(cutoff.getMonth() + 1) +
        '-' + pad(cutoff.getDate());
      return stamp >= ymd;  // ISO date strings compare lexicographically
    }
    const days = parseInt(timeWin.value, 10);
    if (!days) return true;
    return (Date.now() - Date.parse(stamp)) <= days * 864e5;
  }
  function apply() {
    const needle = (q.value || '').toLowerCase();
    const floor = parseInt(minScore.value, 10) || 0;
    minLabel.textContent = floor;
    let shown = 0;
    rows.forEach(function (tr) {
      const hay = tr.getAttribute('data-hay');
      const best = parseInt(tr.getAttribute('data-best'), 10) || 0;
      const ok = (!needle || hay.indexOf(needle) !== -1) && best >= floor && inWindow(tr);
      tr.style.display = ok ? '' : 'none';
      if (ok) shown += 1;
    });
    document.getElementById('shown-count').textContent = shown;
    const empty = document.getElementById('filter-empty');
    if (empty) empty.style.display = shown ? 'none' : '';
    return shown;
  }
  q.addEventListener('input', apply);
  minScore.addEventListener('input', apply);
  const note = document.getElementById('timewin-note');
  timeWin.addEventListener('change', function () { note.textContent = ''; apply(); });
  let sortState = {};
  const sortHeaders = Array.from(document.querySelectorAll('th[data-sort]'));
  sortHeaders.forEach(function (th) {
    th.setAttribute('tabindex', '0');
    th.setAttribute('role', 'button');
    const ind = document.createElement('span');
    ind.className = 'sort-ind';
    th.appendChild(ind);
    function doSort() {
      const key = th.getAttribute('data-sort');
      const numeric = th.getAttribute('data-num') === '1';
      sortState[key] = !sortState[key];
      const dir = sortState[key] ? 1 : -1;
      sortHeaders.forEach(function (h) {
        h.querySelector('.sort-ind').textContent = '';
        h.removeAttribute('aria-sort');
      });
      ind.textContent = dir === 1 ? '\\u25b4' : '\\u25be';
      th.setAttribute('aria-sort', dir === 1 ? 'ascending' : 'descending');
      const tbody = document.getElementById('jobs');
      rows.sort(function (a, b) {
        let av = a.getAttribute('data-' + key) || '';
        let bv = b.getAttribute('data-' + key) || '';
        if (numeric) { av = parseFloat(av) || 0; bv = parseFloat(bv) || 0; }
        return av < bv ? -dir : av > bv ? dir : 0;
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    }
    th.addEventListener('click', doSort);
    th.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); doSort(); }
    });
  });
  // Start at "since yesterday", but never present an empty page when older
  // matches exist: widen the window until something shows.
  (function () {
    const order = ['yesterday', '3', '7', '30', '0'];
    const labels = {'3': 'last 3 days', '7': 'last 7 days',
                    '30': 'last 30 days', '0': 'any time'};
    let i = order.indexOf(timeWin.value);
    while (apply() === 0 && rows.length > 0 && i < order.length - 1) {
      i += 1;
      timeWin.value = order[i];
    }
    if (i > 0 && timeWin.value === order[i]) {
      note.textContent = 'nothing posted since yesterday, widened to ' + labels[order[i]];
    }
  })();
  // Active-run progress: poll the local jobbot dashboard while a run is
  // going. Same reachability rules as the Run now button: the panel only
  // appears when this page is open on the machine running jobbot.
  const arPanel = document.getElementById('active-run');
  const AR_URL = 'http://127.0.0.1:5001/api/runs/active';
  let arTimer = null;
  function arSchedule(ms) {
    clearTimeout(arTimer);
    arTimer = setTimeout(pollActiveRun, ms);
  }
  function fmtClock(iso) {
    const d = new Date(iso);
    return isNaN(d) ? '' : d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
  }
  // The pulse is a LIVENESS signal, not decoration: it animates only
  // while progress rows keep moving. Progress updates land per item and
  // a single generation call can honestly take a few minutes, so only
  // 5+ minutes of silence counts as stuck (pulse stops, note appears).
  const AR_STALL_S = 300;
  function fmtWhen(iso) {
    // Clock time alone misleads once the run is a day old: "18:31" reads
    // as today. Prefix the date whenever it isn't.
    const d = new Date(iso);
    if (isNaN(d)) return '';
    const clock = d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    return d.toDateString() === new Date().toDateString()
      ? clock
      : d.toLocaleDateString([], {month: 'short', day: 'numeric'}) + ' ' + clock;
  }
  // Peripheral + out-of-tab signals for an in-flight run. The rail shows the
  // ACTIVE stage's progress, not a synthesised whole-run percentage: stages
  // are wildly unequal (35 searches take a minute, 200 scoring calls take
  // 25), so a single global number would be fiction. State honesty first.
  const AR_BASE_TITLE = document.title;
  let arTick = null;
  function setRunSignals(stageLabel, done, total, startedAt) {
    const rail = document.getElementById('run-rail');
    const pct = total ? Math.min(100, Math.round(done / total * 100)) : 0;
    // Below 2% a determinate rail is indistinguishable from an empty one, so
    // fall back to the travelling segment until there is progress to show.
    const vague = pct < 2;
    rail.classList.toggle('indeterminate', vague);
    rail.firstElementChild.style.width = vague ? '' : pct + '%';
    rail.hidden = false;
    document.title = '▶ ' + done + '/' + total + ' ' + stageLabel
      + ' · ' + AR_BASE_TITLE;
    clearInterval(arTick);
    const el = document.getElementById('ar-elapsed');
    const paint = function () {
      const t0 = Date.parse(startedAt);
      if (isNaN(t0)) { el.textContent = ''; return; }
      const s = Math.max(0, Math.round((Date.now() - t0) / 1000));
      const m = Math.floor(s / 60);
      el.textContent = m >= 1 ? ' running ' + m + 'm ' + (s % 60) + 's'
                              : ' running ' + s + 's';
    };
    paint();
    arTick = setInterval(paint, 1000);
    document.getElementById('run-stop').hidden = false;
  }
  function clearRunSignals() {
    document.getElementById('run-rail').hidden = true;
    document.getElementById('ar-elapsed').textContent = '';
    document.title = AR_BASE_TITLE;
    clearInterval(arTick);
    arTick = null;
    const stop = document.getElementById('run-stop');
    stop.hidden = true;
    stop.disabled = false;
  }
  function renderActiveRun(run, finished) {
    arPanel.classList.toggle('live', !finished);
    if (finished) clearRunSignals();
    document.getElementById('ar-title').textContent =
      finished ? 'Last run' : 'Active run';
    document.getElementById('ar-id').textContent = '#' + run.id;
    const started = new Date(run.started_at);
    const dot = document.getElementById('ar-dot');
    const meta = document.getElementById('ar-meta');
    if (finished) {
      const ended = new Date(run.finished_at);
      const took = (isNaN(started) || isNaN(ended)) ? null
        : Math.max(0, Math.round((ended - started) / 60000));
      dot.className = 'done';
      meta.className = 'meta';
      meta.textContent =
        'started ' + fmtWhen(run.started_at) +
        ', finished ' + fmtWhen(run.finished_at) +
        (took === null ? '' : ', took ' + (took < 1 ? '<1' : took) + ' min');
    } else {
      const mins = isNaN(started) ? null : Math.max(0, Math.round((Date.now() - started) / 60000));
      const lastAct = new Date(run.last_activity);
      const ageS = isNaN(lastAct) ? null : Math.max(0, (Date.now() - lastAct) / 1000);
      const stalled = ageS !== null && ageS > AR_STALL_S;
      dot.className = stalled ? 'stalled' : 'running';
      meta.className = stalled ? 'meta stalled-note' : 'meta';
      meta.textContent =
        'started ' + fmtWhen(run.started_at) +
        (mins === null ? '' : ', running for ' + mins + ' min') +
        (stalled
          ? ', no progress for ' + Math.round(ageS / 60) + ' min, run may be stuck'
          : ', last activity ' + fmtClock(run.last_activity));
    }
    const holder = document.getElementById('ar-stages');
    holder.textContent = '';
    // Fixed pipeline order. Later stages only start once earlier ones
    // feed them, so a stage with no items yet reads "waiting", never 0/0.
    const ORDER = ['scrape', 'enrichment', 'scoring', 'generation',
                   'tailored_rescore', 'apply'];
    // Display names mirror the product flow: scrape PO/PM postings ->
    // score vs the general CV -> tailor CV for 80%+ -> rescore tailored.
    const STAGE_LABELS = {
      scrape: 'search job boards',
      enrichment: 'fetch details',
      scoring: 'score vs base CV',
      generation: 'tailor CV + letter',
      tailored_rescore: 'rescore tailored',
      apply: 'apply'
    };
    // A bare "29/29" or "100/100" reads as a percentage. Name the unit so
    // the number is unambiguous: 29 searches (across 14 boards), 100
    // postings fetched, 63 postings scored, 37 packages tailored.
    const STAGE_UNITS = {
      scrape: 'searches',
      enrichment: 'postings',
      scoring: 'postings',
      generation: 'packages',
      tailored_rescore: 'packages',
      apply: 'applications'
    };
    const byName = {};
    (run.stages || []).forEach(function (s) { byName[s.stage] = s; });
    const doneOf = function (s) {
      return (Number(s.completed) || 0) + (Number(s.failed) || 0) + (Number(s.skipped) || 0);
    };
    const hasActivity = function (s) {
      return s && ((Number(s.started) || 0) > 0 || doneOf(s) > 0);
    };
    let lastActiveIdx = -1;
    ORDER.forEach(function (n, i) { if (hasActivity(byName[n])) lastActiveIdx = i; });
    let currentLabel = '';
    let headerEta = '';
    let scoringMeta = null;
    let enrichMeta = null;
    ORDER.forEach(function (stageName, i) {
      const s = byName[stageName];
      const isCore = i < 4;  // scrape/enrichment/scoring/generation always shown
      if (!hasActivity(s)) {
        if (!isCore) return;  // rescore/apply appear only when they run
        const row = document.createElement('div');
        row.className = 'stagerow';
        const name = document.createElement('span');
        name.className = 'sname';
        name.textContent = STAGE_LABELS[stageName] || stageName;
        const state = document.createElement('span');
        state.className = 'meta';
        // A bare "waiting" tells the user nothing about why. Name the stage
        // it is queued behind, so the panel reads as a chain rather than as
        // four independent things that might be stuck. On a finished run
        // nothing is coming anymore, so "waiting" would be a lie.
        if (i <= lastActiveIdx) {
          state.textContent = 'nothing to do';
        } else if (finished) {
          state.textContent = 'did not run';
        } else {
          const blocker = ORDER.slice(0, i).reverse()
            .find(function (n) { return hasActivity(byName[n]); });
          state.textContent = blocker
            ? 'waiting for ' + (STAGE_LABELS[blocker] || blocker)
            : 'waiting to start';
        }
        row.appendChild(name); row.appendChild(state);
        holder.appendChild(row);
        return;
      }
      const total = Number(s.total) || 0;
      const done = doneOf(s);
      const isActive = !finished && i === lastActiveIdx && done < total;
      const row = document.createElement('div');
      row.className = 'stagerow';
      const name = document.createElement('span');
      name.className = 'sname';
      name.textContent = STAGE_LABELS[stageName] || stageName;
      const bar = document.createElement('span');
      // `working` adds the moving sheen; only the stage actually in flight
      // gets it, so the eye lands on where the run currently is.
      bar.className = 'bar' + (isActive ? ' working' : '');
      const fill = document.createElement('i');
      fill.style.width = (total ? Math.min(100, Math.round(done / total * 100)) : 100) + '%';
      bar.appendChild(fill);
      const meta2 = s.metadata || {};
      const num = document.createElement('span');
      num.className = 'snum' + (Number(s.failed) ? ' sfail' : '');
      let numTxt = done + '/' + total;
      const unit = STAGE_UNITS[stageName];
      if (unit) numTxt += ' ' + unit;
      if (stageName === 'scrape' && meta2.boards) {
        numTxt += ' across ' + meta2.boards + ' job boards';
      }
      if (stageName === 'enrichment' && meta2.retries > 0) {
        numTxt += ' (' + (meta2.new || 0) + ' new + '
                + meta2.retries + ' retries)';
      }
      if (stageName === 'scoring' && meta2.backlog > 0) {
        numTxt += ' (' + (meta2.from_this_run || 0) + ' new + '
                + meta2.backlog + ' backlog)';
      }
      if (Number(s.failed)) numTxt += ', ' + s.failed + ' failed';
      if (Number(s.skipped)) numTxt += ', ' + s.skipped + ' skipped';
      if (!isActive && done < total) numTxt += ', ' + (total - done) + ' not run';
      const el = stageElapsed(meta2, s, isActive);
      if (el) numTxt += ', ' + el;
      if (isActive) {
        const eta = etaMinutes(stageName, done, total);
        if (eta !== null) {
          numTxt += ', ~' + eta + ' min left';
          headerEta = '~' + eta + ' min left in ' + (STAGE_LABELS[stageName] || stageName);
        }
      }
      num.textContent = numTxt;
      row.appendChild(name); row.appendChild(bar); row.appendChild(num);
      holder.appendChild(row);
      // Funnel note between "search job boards" and "fetch details": the
      // narrowing from 333 found to 13 fetches is dedup + the age gate, and
      // saying so is the difference between "efficient" and "broken".
      if (stageName === 'scrape') {
        const em = ((byName['enrichment'] || {}).metadata) || {};
        const fr = document.createElement('div');
        fr.className = 'funnelrow';
        if (em.found != null) {
          let t = 'of ' + em.found + ' found: ' + (em.already_seen || 0)
                + ' already known';
          if (em.too_old) t += ', ' + em.too_old + ' too old';
          t += ' → ' + (em.new || 0) + ' to fetch';
          if (em.retries) {
            t += ', plus ' + em.retries + ' retries from earlier runs';
          }
          if (em.deferred_over_cap) {
            t += ' (' + em.deferred_over_cap + ' deferred to next run)';
          }
          fr.textContent = t;
          holder.appendChild(fr);
        } else if (meta2.hits_so_far != null && done > 0) {
          fr.textContent = meta2.hits_so_far + ' found so far, '
            + Math.max(0, meta2.hits_so_far - (meta2.new_so_far || 0))
            + ' already known, ' + (meta2.new_so_far || 0) + ' new';
          holder.appendChild(fr);
        }
      }
      if (isActive) {
        setRunSignals(STAGE_LABELS[stageName] || stageName, done, total,
                      run.started_at);
      }
      if (isActive && s.current_label) currentLabel = (STAGE_LABELS[stageName] || stageName) + ': ' + s.current_label;
      if (stageName === 'enrichment') enrichMeta = meta2;
      if (stageName === 'scoring') scoringMeta = meta2;
    });
    const cur = document.getElementById('ar-current');
    cur.textContent = currentLabel ? 'working on ' + currentLabel : '';
    if (headerEta) {
      document.getElementById('ar-meta').textContent += ', ' + headerEta;
    }
    renderTicker(scoringMeta, enrichMeta);
    arPanel.hidden = false;
  }
  function stageElapsed(meta2, s, isActive) {
    const t0 = Date.parse(meta2.stage_started_at || '');
    if (isNaN(t0)) return '';
    const t1 = isActive ? Date.now() : Date.parse(s.updated_at || '');
    if (isNaN(t1) || t1 <= t0) return '';
    const m = Math.round((t1 - t0) / 60000);
    return m < 1 ? '<1 min' : m + ' min';
  }
  function renderStuckWarning(d) {
    // Only speak up once the stall is longer than any healthy run (90 min
    // is the record), so a slow-but-working run is not called stuck.
    const el = document.getElementById('ar-stuck');
    const h = Number(d.stuck_for_hours);
    if (!d.stale_run_id || !(h >= 3)) { el.hidden = true; return; }
    el.textContent = 'run #' + d.stale_run_id + ' has been stuck for '
      + Math.round(h) + 'h and is blocking every scheduled run behind it.'
      + ' Kill it on the host, then press Run now.';
    el.hidden = false;
  }
  function renderTicker(meta2, emeta) {
    const strong = document.getElementById('ar-strong');
    const ticker = document.getElementById('ar-ticker');
    const fails = document.getElementById('ar-fails');
    if (!meta2 && !emeta) { strong.hidden = ticker.hidden = fails.hidden = true; return; }
    meta2 = meta2 || {};
    const thr = meta2.strong_threshold || 80;
    if (meta2.n_strong > 0) {
      strong.textContent = meta2.n_strong + ' match' +
        (meta2.n_strong === 1 ? '' : 'es') + ' at ' + thr + '+ this run';
      strong.hidden = false;
    } else { strong.hidden = true; }
    const ticks = (meta2.ticker || []).slice().reverse();
    ticker.textContent = '';
    ticks.forEach(function (t) {
      const chip = document.createElement('span');
      chip.className = 'tick' + (Number(t.s) >= thr ? ' hit' : '');
      const score = document.createElement('b');
      score.textContent = t.s;
      chip.appendChild(document.createTextNode((t.c || '?') + ' '));
      chip.appendChild(score);
      ticker.appendChild(chip);
    });
    ticker.hidden = ticks.length === 0;
    const parts = [];
    // Fetch failures grouped by board: 84 individual "failed" ticks are
    // noise, "brainville ×37, dailyremote ×17" is a diagnosis.
    const fb = (emeta && emeta.fail_by_source) || null;
    if (fb) {
      const srcs = Object.keys(fb).sort(function (a, b) { return fb[b] - fb[a]; })
        .map(function (k) { return k + ' ×' + fb[k]; }).join(', ');
      if (srcs) parts.push('could not fetch details: ' + srcs);
    }
    if (emeta && emeta.gave_up) {
      parts.push('gave up on ' + emeta.gave_up + ' dead page' +
        (emeta.gave_up === 1 ? '' : 's') + ' (3 failed tries)');
    }
    // Permanently closed rows: walled boards and disabled sources are
    // resolved without a fetch and never retried again.
    const wb = (emeta && emeta.walled_by_source) || null;
    if (wb) {
      const wr = (emeta && emeta.walled_reasons) || {};
      const srcs = Object.keys(wb).sort(function (a, b) { return wb[b] - wb[a]; })
        .map(function (k) {
          return k + ' ×' + wb[k] + (wr[k] ? ' (' + wr[k] + ')' : '');
        }).join(', ');
      if (srcs) parts.push("won't retry: " + srcs);
    }
    const fl = meta2.failures || [];
    if (fl.length) {
      parts.push('could not score: ' + fl.slice().reverse()
        .map(function (f) { return (f.c || '?') + ' (' + (f.e || 'error') + ')'; })
        .join(', '));
    }
    if (parts.length) {
      fails.textContent = parts.join(' · ');
      fails.hidden = false;
    } else { fails.hidden = true; }
  }
  // Rolling throughput per stage, measured between polls, for an honest
  // "~N min left" (scoring runs ~30-60s per posting on the Max plan; a
  // slow bar is not a stuck bar).
  const arRates = {};
  function etaMinutes(stage, done, total) {
    const now = Date.now();
    const prev = arRates[stage];
    if (!prev) { arRates[stage] = {t: now, done: done, rate: 0}; return null; }
    const dt = (now - prev.t) / 1000;
    if (dt >= 15) {
      const r = (done - prev.done) / dt;  // items per second
      prev.rate = prev.rate ? (0.6 * prev.rate + 0.4 * r) : r;
      prev.t = now; prev.done = done;
    }
    if (!prev.rate || prev.rate <= 0) return null;
    return Math.max(1, Math.round((total - done) / prev.rate / 60));
  }
  function pollActiveRun() {
    fetch(AR_URL)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.active) { renderActiveRun(d.run); arSchedule(5000); }
        // Idle: keep the last finished run on screen instead of hiding
        // the panel at the exact moment it has the most to say.
        else if (d.last_run) {
          renderActiveRun(d.last_run, true);
          // A wedged run holds the single-run lock, so every scheduled run
          // behind it is skipped. Showing only the last good run made a
          // 32-hour stall look like a quiet day.
          renderStuckWarning(d);
          arSchedule(30000);
        }
        else { clearRunSignals(); arPanel.hidden = true; arSchedule(60000); }
      })
      // Local dashboard unreachable: drop the rail and the tab-title marker
      // rather than leaving a run that looks eternally in flight.
      .catch(function () { clearRunSignals(); arPanel.hidden = true; arSchedule(120000); });
  }
  pollActiveRun();
  // "Run now": POST to the jobbot dashboard on the machine that runs the
  // pipeline. Only reachable when this page is opened on that machine
  // (or its network) with `jobbot dashboard` up; the run republishes
  // this site when it finishes.
  const runBtn = document.getElementById('run-now');
  const runStatus = document.getElementById('run-now-status');
  runBtn.addEventListener('click', function () {
    runBtn.disabled = true;
    runStatus.textContent = 'contacting local dashboard…';
    fetch('http://127.0.0.1:5001/api/runs/trigger', {method: 'POST'})
      .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, d: d}; }); })
      .then(function (x) {
        if (x.ok) {
          runStatus.textContent = 'run started; this page republishes when it finishes (typically under an hour)';
          arSchedule(3000);
        } else if (x.d && x.d.status === 'already_running') {
          runStatus.textContent = 'a run is already in progress';
          runBtn.disabled = false;
        } else {
          runStatus.textContent = 'trigger failed, check the local dashboard';
          runBtn.disabled = false;
        }
      })
      .catch(function () {
        runStatus.textContent = 'local dashboard not reachable: open this page on the Mac running jobbot and make sure `jobbot dashboard` is running';
        runBtn.disabled = false;
      });
  });
  // Kill switch. The pipeline checks for a stop request between items, so a
  // long LLM call already in flight has to return first: the copy says
  // "stopping" and stays until the panel reports the run finished, rather
  // than claiming success the moment the POST returns.
  const stopBtn = document.getElementById('run-stop');
  stopBtn.addEventListener('click', function () {
    stopBtn.disabled = true;
    runStatus.textContent = 'asking the run to stop…';
    fetch('http://127.0.0.1:5001/api/runs/stop', {method: 'POST'})
      .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, d: d}; }); })
      .then(function (x) {
        if (x.ok) {
          runStatus.textContent = 'stopping after the current item finishes; '
            + 'a scoring or tailoring call in flight can take a minute';
          arSchedule(3000);
        } else if (x.d && x.d.status === 'no_active_run') {
          runStatus.textContent = 'no run is in progress';
          stopBtn.hidden = true;
        } else {
          runStatus.textContent = 'stop request failed, check the local dashboard';
          stopBtn.disabled = false;
        }
      })
      .catch(function () {
        runStatus.textContent = 'local dashboard not reachable, so the run cannot be stopped from here';
        stopBtn.disabled = false;
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


_MAX_LOCATIONS_SHOWN = 2
# "City, Region, Country" is ONE place, and that is how LinkedIn writes every
# location ("Munich, Bavaria, Germany"). Only past three parts is a value
# actually a LIST of sites, which is the case worth collapsing. Measured on
# the live table: a 2-part threshold turned 89 ordinary rows into
# "Munich, Bavaria +1 more", which is worse than the original.
_HIERARCHY_MAX_PARTS = 3


def _short_location(raw: str | None) -> str:
    """Collapse a multi-SITE location list to the first sites plus a count.

    German boards ship things like "Essen,Fürstenwalde/Spree,Hamburg,Hannover,
    Helmstedt,Landshut,Potsdam,Regensburg" with no spaces after the commas, so
    the browser finds no wrap opportunity, the cell refuses to narrow, and
    every other column is squeezed until titles stack five lines deep and the
    row grows to ~140px. Abbreviating keeps rows scannable; the full string
    stays in the cell's title attribute and in data.json, so nothing is lost.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) <= _HIERARCHY_MAX_PARTS:
        # One place, however it was punctuated. Re-join with spaces so the
        # cell has somewhere to wrap even when the source had none.
        return ", ".join(parts)
    shown = ", ".join(parts[:_MAX_LOCATIONS_SHOWN])
    return f"{shown} +{len(parts) - _MAX_LOCATIONS_SHOWN} more"


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
    posted_stamp = str(job["posted_at"] or first_seen or "")[:10]
    return (
        f'<tr data-hay="{hay}" data-best="{best}" data-score="{job["score"] or 0}"'
        f' data-posted="{e(posted_stamp)}"'
        f' data-tailored="{job["score_tailored"] or 0}"'
        f' data-company="{e((job["company"] or "").lower())}"'
        f' data-seen="{e(first_seen)}">'
        f'<td><span class="cname" title="{e(job["company"])}">{e(job["company"])}</span>'
        f'<div class="src">{e(job["source"])}</div></td>'
        f'<td><a class="titlelink" href="{e(job["url"])}" target="_blank"'
        f' rel="noopener" title="{e(job["title"])}">{e(job["title"])}</a>{newpill}</td>'
        f'<td class="loc"><span class="loctext" title="{e(job["location"] or "")}">'
        f'{e(_short_location(job["location"]))}</span></td>'
        f'<td>{e(job["salary"] or "")}</td>'
        f'<td>{_score_badge(job["score"])}</td>'
        f'<td>{_score_badge(job["score_tailored"])}</td>'
        f'<td>{apply_cell}</td>'
        f'<td>{docs_cell}</td>'
        f'<td class="meta">{_fmt_ts(first_seen)}</td>'
        f'</tr>'
    )


def render_index_html(config: Config, jobs: list[dict], runs: list[dict],
                      now: datetime, unsent_all_time: int | None = None) -> str:
    e = html.escape
    # The newest FINISHED run; an in-flight or abandoned row has only
    # zeros and would misreport the last real pass as "0 fetched".
    latest = next((r for r in runs if r["finished_at"]), runs[0] if runs else None)
    # The old bar led with len(jobs), which is just `publish.max_jobs` once
    # the corpus outgrows it: it read "300 matches" every single day and
    # answered a question nobody has. What the user acts on is: what showed
    # up today, how much of that cleared the tailoring bar, and what is
    # sitting finished and unsent.
    today_iso = now.date().isoformat()
    is_new_today = lambda j: (j["first_seen_at"] or "")[:10] == today_iso  # noqa: E731
    best = lambda j: j["score_tailored"] if j["score_tailored"] is not None else (j["score"] or 0)  # noqa: E731
    bar = config.digest.generate_docs_above_score

    new_today = sum(1 for j in jobs if is_new_today(j))
    hot_today = sum(1 for j in jobs if is_new_today(j) and best(j) >= bar)
    # Finished packages that have not gone out yet: the actual to-do list.
    # Counted over ALL time, not just the table's window, because a package
    # built six weeks ago and never sent is still owed an action. Falls back
    # to the window when the caller has no DB handle (tests).
    unsent = unsent_all_time if unsent_all_time is not None else sum(
        1 for j in jobs
        if j["documents"] and j["status"] not in (
            "apply_submitted", "apply_queued", "employer_received",
            "rejected", "interview_invited", "listing_expired",
        )
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
            latest_line += f', <span class="err">{latest["n_errors"]} errors</span>'

    job_rows = "\n".join(_job_row_html(j, now) for j in jobs)
    if not jobs:
        empty_msg = "No postings to show for this window."
        if latest and latest["n_errors"]:
            empty_msg += (f" The latest run reported {latest['n_errors']} errors;"
                          " scoring may be failing (check API credits and logs).")
        job_rows = (f'<tr><td colspan="9" class="meta" style="text-align:center;'
                    f'padding:28px">{e(empty_msg)}</td></tr>')
    else:
        job_rows += ('\n<tr id="filter-empty" style="display:none"><td colspan="9"'
                     ' class="meta" style="text-align:center;padding:28px">'
                     'Nothing matches the current filters. Widen the posted-time'
                     ' window or lower the score floor.</td></tr>')
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
<div id="run-rail" hidden aria-hidden="true"><i></i></div>
<main>
  <div class="header">
    <h1>{e(config.publish.site_title)}</h1>
    <span class="actions">
      <span id="run-now-status" class="meta"></span>
      <button id="run-stop" class="btn btn-stop" type="button" hidden
        title="Asks the running pipeline to stop at its next checkpoint">Stop run</button>
      <button id="run-now" class="btn" type="button"
        title="Starts a pipeline run on the Mac running jobbot (needs jobbot dashboard up)">Run now</button>
      <span class="meta">Generated {e(_fmt_ts(now.isoformat()))} UTC</span>
    </span>
  </div>
  <div id="active-run" hidden>
    <div class="arhead">
      <h2><span id="ar-dot" class="running"></span><span id="ar-title">Active run</span> <span id="ar-id"></span><span id="ar-elapsed" class="runstate"></span></h2>
      <span class="meta" id="ar-meta"></span>
    </div>
    <div id="ar-stages"></div>
    <div class="meta" id="ar-current" style="margin-top:8px"></div>
    <div id="ar-strong" hidden></div>
    <div id="ar-ticker" hidden></div>
    <div id="ar-stuck" hidden></div>
    <div id="ar-fails" hidden></div>
  </div>
  <div class="statbar">
    <span class="stat"><span class="num">{new_today}</span><span class="lbl">new today</span></span>
    <span class="sep">|</span>
    <span class="stat hot"><span class="num">{hot_today}</span><span class="lbl">of those {bar}+</span></span>
    <span class="sep">|</span>
    <span class="stat"><span class="num">{unsent}</span><span class="lbl">packages waiting to be sent</span></span>
    <span class="sep">|</span>
    <span class="stat"><span class="num" id="shown-count">{len(jobs)}</span><span class="lbl">rows shown</span></span>
  </div>
  <p class="runline">{latest_line}</p>
  <div class="controls">
    <input id="q" type="search" placeholder="Filter by company, title, location, source">
    <label>Posted
      <select id="timewin">
        <option value="yesterday">since yesterday</option>
        <option value="3">last 3 days</option>
        <option value="7">last 7 days</option>
        <option value="30">last 30 days</option>
        <option value="0">any time</option>
      </select>
      <span id="timewin-note" class="meta"></span>
    </label>
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
