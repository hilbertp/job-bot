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
.header .actions { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.meta { color: var(--muted); font-size: 13px; }
.btn { background: var(--accent); color: var(--bg); border: none; border-radius: 8px;
  padding: 8px 14px; font-weight: 650; font-size: 13px; cursor: pointer;
  font-family: inherit; }
.btn:hover { filter: brightness(1.12); }
.btn:disabled { opacity: 0.55; cursor: default; filter: none; }
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
#active-run { background: var(--panel); border: 1px solid var(--line);
  border-radius: 10px; padding: 14px 16px; margin-bottom: 18px; }
#active-run h2 { margin: 0; font-size: 14px; }
#ar-dot { display: inline-block; width: 9px; height: 9px; border-radius: 999px;
  margin-right: 7px; vertical-align: 1px; }
#ar-dot.running { background: var(--good);
  animation: ar-pulse 1.4s cubic-bezier(0.25, 1, 0.5, 1) infinite; }
#ar-dot.stalled { background: var(--mid); animation: none; }
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
.stagerow .snum { flex: 0 0 110px; text-align: right;
  font-variant-numeric: tabular-nums; }
.stagerow .sfail { color: var(--mid); }
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
  function renderActiveRun(run) {
    document.getElementById('ar-id').textContent = '#' + run.id;
    const started = new Date(run.started_at);
    const mins = isNaN(started) ? null : Math.max(0, Math.round((Date.now() - started) / 60000));
    const lastAct = new Date(run.last_activity);
    const ageS = isNaN(lastAct) ? null : Math.max(0, (Date.now() - lastAct) / 1000);
    const stalled = ageS !== null && ageS > AR_STALL_S;
    const dot = document.getElementById('ar-dot');
    dot.className = stalled ? 'stalled' : 'running';
    const meta = document.getElementById('ar-meta');
    meta.className = stalled ? 'meta stalled-note' : 'meta';
    meta.textContent =
      'started ' + fmtClock(run.started_at) +
      (mins === null ? '' : ', running for ' + mins + ' min') +
      (stalled
        ? ', no progress for ' + Math.round(ageS / 60) + ' min, run may be stuck'
        : ', last activity ' + fmtClock(run.last_activity));
    const holder = document.getElementById('ar-stages');
    holder.textContent = '';
    // Fixed pipeline order. Later stages only start once earlier ones
    // feed them, so a stage with no items yet reads "waiting", never 0/0.
    const ORDER = ['scrape', 'enrichment', 'scoring', 'generation',
                   'tailored_rescore', 'apply'];
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
    ORDER.forEach(function (stageName, i) {
      const s = byName[stageName];
      const isCore = i < 4;  // scrape/enrichment/scoring/generation always shown
      if (!hasActivity(s)) {
        if (!isCore) return;  // rescore/apply appear only when they run
        const row = document.createElement('div');
        row.className = 'stagerow';
        const name = document.createElement('span');
        name.className = 'sname';
        name.textContent = stageName;
        const state = document.createElement('span');
        state.className = 'meta';
        state.textContent = i <= lastActiveIdx ? 'no items' : 'waiting';
        row.appendChild(name); row.appendChild(state);
        holder.appendChild(row);
        return;
      }
      const total = Number(s.total) || 0;
      const done = doneOf(s);
      const isActive = i === lastActiveIdx && done < total;
      const row = document.createElement('div');
      row.className = 'stagerow';
      const name = document.createElement('span');
      name.className = 'sname';
      name.textContent = stageName;
      const bar = document.createElement('span');
      bar.className = 'bar';
      const fill = document.createElement('i');
      fill.style.width = (total ? Math.min(100, Math.round(done / total * 100)) : 100) + '%';
      bar.appendChild(fill);
      const num = document.createElement('span');
      num.className = 'snum' + (Number(s.failed) ? ' sfail' : '');
      let numTxt = done + '/' + total;
      if (Number(s.failed)) numTxt += ', ' + s.failed + ' failed';
      if (Number(s.skipped)) numTxt += ', ' + s.skipped + ' skipped';
      if (!isActive && done < total) numTxt += ', ' + (total - done) + ' not run';
      if (isActive) {
        const eta = etaMinutes(stageName, done, total);
        if (eta !== null) numTxt += ', ~' + eta + ' min left';
      }
      num.textContent = numTxt;
      row.appendChild(name); row.appendChild(bar); row.appendChild(num);
      holder.appendChild(row);
      if (isActive && s.current_label) currentLabel = stageName + ': ' + s.current_label;
    });
    const cur = document.getElementById('ar-current');
    cur.textContent = currentLabel ? 'working on ' + currentLabel : '';
    arPanel.hidden = false;
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
        else { arPanel.hidden = true; arSchedule(60000); }
      })
      .catch(function () { arPanel.hidden = true; arSchedule(120000); });
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
    posted_stamp = str(job["posted_at"] or first_seen or "")[:10]
    return (
        f'<tr data-hay="{hay}" data-best="{best}" data-score="{job["score"] or 0}"'
        f' data-posted="{e(posted_stamp)}"'
        f' data-tailored="{job["score_tailored"] or 0}"'
        f' data-company="{e((job["company"] or "").lower())}"'
        f' data-seen="{e(first_seen)}">'
        f'<td>{e(job["company"])}<div class="src">{e(job["source"])}</div></td>'
        f'<td><a class="titlelink" href="{e(job["url"])}" target="_blank"'
        f' rel="noopener">{e(job["title"])}</a>{newpill}</td>'
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
    # The newest FINISHED run; an in-flight or abandoned row has only
    # zeros and would misreport the last real pass as "0 fetched".
    latest = next((r for r in runs if r["finished_at"]), runs[0] if runs else None)
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
<main>
  <div class="header">
    <h1>{e(config.publish.site_title)}</h1>
    <span class="actions">
      <span id="run-now-status" class="meta"></span>
      <button id="run-now" class="btn" type="button"
        title="Starts a pipeline run on the Mac running jobbot (needs jobbot dashboard up)">Run now</button>
      <span class="meta">Generated {e(_fmt_ts(now.isoformat()))} UTC</span>
    </span>
  </div>
  <div class="statbar">
    <span class="stat"><span class="num">{len(jobs)}</span><span class="lbl">matches</span></span>
    <span class="sep">|</span>
    <span class="stat"><span class="num">{new_today}</span><span class="lbl">new today</span></span>
    <span class="sep">|</span>
    <span class="stat"><span class="num">{with_docs}</span><span class="lbl">ready-to-send packages</span></span>
    <span class="sep">|</span>
    <span class="stat"><span class="num" id="shown-count">{len(jobs)}</span><span class="lbl">after filters</span></span>
  </div>
  <p class="runline">{latest_line}</p>
  <div id="active-run" hidden>
    <div class="arhead">
      <h2><span id="ar-dot" class="running"></span>Active run <span id="ar-id"></span></h2>
      <span class="meta" id="ar-meta"></span>
    </div>
    <div id="ar-stages"></div>
    <div class="meta" id="ar-current" style="margin-top:8px"></div>
  </div>
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
