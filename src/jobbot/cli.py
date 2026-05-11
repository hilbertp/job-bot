"""CLI entrypoint: `jobbot <command>`."""
from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import load_config, load_secrets
from .models import JobStatus
from .pipeline import daily_digest, run_with_failure_alerts
from .profile_distiller import rebuild_compiled_profile
from .profile_distiller.website_fetcher import fetch_website
from .scrapers import REGISTRY
from .state import connect, db_lock_status

console = Console()


def cmd_run(_args) -> int:
    result = run_with_failure_alerts(load_config(), load_secrets())

    fetched = result.get("n_fetched", 0)
    new = result.get("n_new", 0)
    generated = result.get("n_generated", 0)
    applied = result.get("n_applied", 0)
    errors = result.get("n_errors", 0)
    diagnostics = result.get("diagnostics", {})
    stages = diagnostics.get("stages", {})
    score_stats = diagnostics.get("score_stats", {})
    blockers = diagnostics.get("top_blockers", [])

    progress = (
        f"[cyan]Fetched[/cyan] {fetched} total\n"
        f"[cyan]New[/cyan] {new} unique\n"
        f"[yellow]Generated[/yellow] {generated} CV/CL sets\n"
        f"[green]Applied[/green] {applied} applications"
    )
    if errors:
        progress += f"\n[red]Errors[/red] {errors}"
    console.print(Panel(progress, title="[bold]jobbot · workflow progress[/bold]", border_style="blue"))

    flow = (
        f"fetched {stages.get('fetched', fetched)}"
        f" -> new {stages.get('new', new)}"
        f" -> filtered {stages.get('filtered', 0)}"
        f" -> scored {stages.get('scored', 0)}"
        f" -> below_threshold {stages.get('below_threshold', 0)}"
        f" -> score_failed {stages.get('score_failed', 0)}"
        f" -> generated {stages.get('generated', generated)}"
        f" -> applied {stages.get('applied', applied)}"
    )
    console.print(Panel(flow, title="[bold]Pipeline flow[/bold]", border_style="cyan"))

    if score_stats.get("count", 0):
        score_line = (
            f"scores={score_stats.get('count', 0)} | "
            f"avg={score_stats.get('avg', 0)} | "
            f"min={score_stats.get('min')} | "
            f"max={score_stats.get('max')} | "
            f"threshold={score_stats.get('threshold')}"
        )
        console.print(Panel(score_line, title="[bold]Score summary[/bold]", border_style="magenta"))

    if blockers:
        table = Table(title="Top blockers (why jobs did not progress)")
        table.add_column("reason")
        table.add_column("count", justify="right")
        for item in blockers:
            table.add_row(str(item.get("reason", "unknown")), str(item.get("count", 0)))
        console.print(table)

    if stages.get("score_failed", 0):
        console.print(
            "[red]Fix:[/red] scoring errors usually mean API/network/parser issues. "
            "Check logs and ANTHROPIC_API_KEY first."
        )
    return 0


def cmd_digest(_args) -> int:
    daily_digest(load_config(), load_secrets())
    console.print("daily digest sent")
    return 0


def cmd_status(_args) -> int:
    with connect() as conn:
        table = Table(title="jobbot · job pipeline")
        table.add_column("status"); table.add_column("count", justify="right")
        for st in JobStatus:
            cur = conn.execute("SELECT COUNT(*) FROM seen_jobs WHERE status = ?", (st.value,))
            table.add_row(st.value, str(cur.fetchone()[0]))
    console.print(table)
    return 0


def cmd_sources(_args) -> int:
    table = Table(title="registered scrapers")
    table.add_column("source"); table.add_column("class")
    for name, scr in REGISTRY.items():
        table.add_row(name, type(scr).__name__)
    console.print(table)
    return 0


def cmd_db_status(_args) -> int:
    """Report whether the SQLite writer lock is currently held."""
    status = db_lock_status()
    color = "red" if status.locked else "green"
    state = "LOCKED" if status.locked else "available"
    console.print(f"[{color}]{state}[/{color}] — {status.detail}")
    if status.holders:
        table = Table(title="processes with the DB file open")
        table.add_column("pid"); table.add_column("command")
        for h in status.holders:
            table.add_row(h.get("pid", "?"), h.get("command", "?"))
        console.print(table)
    return 1 if status.locked else 0


def cmd_dashboard(_args) -> int:
    from .dashboard import run as run_dashboard
    console.print("[bold]🤖 jobbot dashboard[/bold] starting on [cyan]http://localhost:5001[/cyan]")
    console.print("Press Ctrl+C to stop")
    run_dashboard()
    return 0


def cmd_enrich_backfill(args) -> int:
    """PRD §7.3 FR-ENR-04 + §7.5 FR-SCO-01: backfill body text for rows that
    were scraped before enrichment was wired in, or that came back below the
    200-word scoring floor. Capped per invocation so repeated runs steadily
    drain the queue without long-running pulls.

    Unlike `enrich_new_postings`, this leaves rows untouched on transient
    fetch failures so a future run can retry. freelance_de rows are
    terminal-marked `cannot_score:source_unsupported` (no fetch_detail
    exists). Use `--source <name>` to restrict to one scraper for
    debugging, and `--dry-run` to log intent without writing.
    """
    from .enrichment.backfill import run_backfill
    from .scoring import MIN_BODY_WORDS
    from .state import jobs_needing_backfill

    if not getattr(args, "backfill", False):
        console.print(
            "[red]Usage:[/red] jobbot enrich --backfill "
            "[--limit N] [--dry-run] [--source NAME]"
        )
        return 2

    cap = int(getattr(args, "limit", 100) or 100)
    dry_run = bool(getattr(args, "dry_run", False))
    source_filter = getattr(args, "source", None)

    with connect() as conn:
        candidates = jobs_needing_backfill(conn, min_words=MIN_BODY_WORDS, limit=cap)
        if not candidates:
            console.print("nothing to backfill — every row has body >= "
                          f"{MIN_BODY_WORDS} words.")
            return 0
        prefix = "DRY-RUN: " if dry_run else ""
        scope = f" (source={source_filter})" if source_filter else ""
        console.print(
            f"{prefix}backfilling up to {len(candidates)} rows{scope} "
            f"(cap {cap}, floor {MIN_BODY_WORDS} words)..."
        )
        report = run_backfill(
            candidates, conn, registry=REGISTRY,
            dry_run=dry_run, source=source_filter,
        )

    table = Table(title="enrichment backfill — per-source success rate")
    table.add_column("source")
    table.add_column("attempted", justify="right")
    table.add_column("succeeded", justify="right")
    table.add_column("failed", justify="right")
    table.add_column("rate", justify="right")
    sources = sorted(set(report.per_source_success) | set(report.per_source_failure))
    for source in sources:
        s = report.per_source_success.get(source, 0)
        f = report.per_source_failure.get(source, 0)
        attempted = s + f
        rate = f"{(100 * s / attempted):.0f}%" if attempted else "—"
        table.add_row(source, str(attempted), str(s), str(f), rate)
    console.print(table)
    console.print(
        f"total: attempted={report.n_attempted}, "
        f"enriched={report.n_enriched}, failed={report.n_failed}, "
        f"unsupported={report.n_unsupported}, "
        f"skipped_by_filter={report.n_skipped_filter}"
    )
    return 0


def cmd_rescore_backfill(args) -> int:
    """Re-score historical Stage-3 jobs whose tailored CV + cover letter are
    on disk but never went through the tailored rescore — usually rows that
    were generated before the rescorer was wired into the pipeline.

    For each candidate row, reads cv.md + cover_letter.md from its output
    directory, calls `llm_score_tailored`, and persists the result via
    `update_score_tailored`. Costs ~1 LLM call per backfilled job.

    With `--base`, this instead enforces PRD §7.5 FR-SCO-01..05: scrub any
    row whose existing `score` was set in violation of the description-
    scraped + 200-word precondition, then re-score every eligible row
    (status in scraped / cannot_score:* with body now backfilled) against
    Sonnet + the PRIMARY_* CV. Costs ~1 LLM call per backfilled job.
    """
    from pathlib import Path

    from .profile import load_profile
    from .scoring import CannotScore, llm_score, llm_score_tailored
    from .state import (
        jobs_needing_base_rescore, jobs_needing_tailored_rescore,
        scrub_stale_scores, update_score_tailored, update_status,
    )
    from .models import JobStatus

    if getattr(args, "base", False):
        return _cmd_rescore_base(args)

    if not getattr(args, "backfill", False):
        console.print("[red]Usage:[/red] jobbot rescore --backfill [--limit N]")
        console.print("[red]   or:[/red] jobbot rescore --base [--limit N]")
        return 2

    cap = int(getattr(args, "limit", 50) or 50)
    secrets = load_secrets()
    profile = load_profile()

    with connect() as conn:
        candidates = jobs_needing_tailored_rescore(conn, limit=cap)
        if not candidates:
            console.print(
                "nothing to backfill — every generated row already has a "
                "tailored score."
            )
            return 0

        console.print(
            f"rescoring {len(candidates)} generated row(s) — "
            f"~1 LLM call each (cap {cap})..."
        )

        table = Table(title="tailored rescore — backfill")
        table.add_column("source"); table.add_column("title")
        table.add_column("base", justify="right")
        table.add_column("tailored", justify="right")
        table.add_column("Δ", justify="right")

        n_ok = n_skipped = n_failed = 0
        for job, output_dir in candidates:
            cv_path = Path(output_dir) / "cv.md"
            cl_path = Path(output_dir) / "cover_letter.md"
            if not (cv_path.exists() and cl_path.exists()):
                console.print(
                    f"[yellow]skip[/yellow] {job.id}: missing cv.md or "
                    f"cover_letter.md under {output_dir}"
                )
                n_skipped += 1
                continue
            try:
                result = llm_score_tailored(
                    job, profile, secrets,
                    tailored_cv_md=cv_path.read_text(),
                    tailored_cover_letter_md=cl_path.read_text(),
                )
            except CannotScore as e:
                console.print(f"[yellow]skip[/yellow] {job.id}: {e}")
                n_skipped += 1
                continue
            except Exception as e:
                console.print(f"[red]fail[/red] {job.id}: {type(e).__name__}: {e}")
                n_failed += 1
                continue

            update_score_tailored(conn, job.id, result.score, result.reason)
            base_row = conn.execute(
                "SELECT score FROM seen_jobs WHERE id = ?", (job.id,)
            ).fetchone()
            base = int(base_row["score"]) if base_row and base_row["score"] is not None else 0
            delta = result.score - base
            delta_str = f"+{delta}" if delta > 0 else str(delta)
            table.add_row(
                job.source, (job.title or "")[:50],
                str(base), str(result.score), delta_str,
            )
            n_ok += 1

        console.print(table)
        console.print(
            f"done: {n_ok} rescored, {n_skipped} skipped, {n_failed} failed"
        )
    return 0 if n_failed == 0 else 1


def _cmd_rescore_base(args) -> int:
    """PRD §7.5 FR-SCO-01..05: scrub legacy scores that violate the
    description-scraped + 200-word precondition, then re-score every row
    that now passes it (status in scraped / cannot_score:*, with a real
    body of >= 200 words) against Sonnet + the PRIMARY_* CV.

    Invoked via `jobbot rescore --base`. Bounded by --limit so a single
    invocation doesn't blow through the API budget on long-tail backlogs.
    """
    from .profile import load_profile
    from .scoring import CannotScore, llm_score
    from .state import (
        jobs_needing_base_rescore, scrub_stale_scores, update_status,
    )
    from .models import JobStatus

    cap = int(getattr(args, "limit", 100) or 100)
    secrets = load_secrets()
    profile = load_profile()

    with connect() as conn:
        n_scrubbed = scrub_stale_scores(conn)
        if n_scrubbed:
            console.print(
                f"[yellow]scrubbed[/yellow] {n_scrubbed} legacy score(s) "
                "that violated the description_scraped/word-count precondition"
            )
        else:
            console.print("no stale scores to scrub")

        candidates = jobs_needing_base_rescore(conn, limit=cap)
        if not candidates:
            console.print(
                "nothing to rescore — every eligible row already has a base score."
            )
            return 0

        console.print(
            f"rescoring {len(candidates)} row(s) with Sonnet + PRIMARY_* CV "
            f"— ~1 LLM call each (cap {cap})..."
        )

        table = Table(title="base rescore — Sonnet + PRIMARY CV")
        table.add_column("source"); table.add_column("title")
        table.add_column("score", justify="right")
        table.add_column("status", justify="right")

        n_ok = n_cannot = n_failed = 0
        for job in candidates:
            try:
                result = llm_score(job, profile, secrets, description_scraped=True)
            except CannotScore as e:
                reason = e.reason
                if reason.startswith("no_primary_cv"):
                    new_status = JobStatus.CANNOT_SCORE_NO_PRIMARY_CV
                else:
                    new_status = JobStatus.CANNOT_SCORE_NO_BODY
                update_status(conn, job.id, new_status, score=None, reason=reason)
                n_cannot += 1
                table.add_row(job.source, (job.title or "")[:50], "—", new_status.value)
                continue
            except Exception as e:
                console.print(f"[red]fail[/red] {job.id}: {type(e).__name__}: {e}")
                n_failed += 1
                continue

            new_status = (
                JobStatus.SCORED if result.score >= 70 else JobStatus.BELOW_THRESHOLD
            )
            update_status(conn, job.id, new_status,
                          score=result.score, reason=result.reason)
            n_ok += 1
            table.add_row(
                job.source, (job.title or "")[:50],
                str(result.score), new_status.value,
            )

        console.print(table)
        console.print(
            f"done: {n_ok} scored, {n_cannot} cannot_score, {n_failed} failed"
        )
    return 0 if n_failed == 0 else 1


def cmd_profile_rebuild(_args) -> int:
    """PRD §7.4 FR-PRO-02: rebuild data/profile.compiled.yaml from corpus."""
    output = rebuild_compiled_profile()
    console.print(f"compiled profile written: {output}")
    return 0


def cmd_profile_fetch_website(_args) -> int:
    """PRD §7.4 FR-PRO-05: crawl true-north.berlin into website corpus."""
    count = fetch_website()
    console.print(f"website corpus refreshed: {count} pages")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jobbot")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run",     help="Run one full pipeline pass.").set_defaults(fn=cmd_run)
    sub.add_parser("digest",  help="Send a digest of the last 24h.").set_defaults(fn=cmd_digest)
    sub.add_parser("status",  help="Show pipeline counts.").set_defaults(fn=cmd_status)
    sub.add_parser("sources", help="List registered scrapers.").set_defaults(fn=cmd_sources)
    sub.add_parser("dashboard", help="Start web dashboard on localhost:5001.").set_defaults(fn=cmd_dashboard)
    sub.add_parser("db-status", help="Show SQLite writer-lock state and any holders.").set_defaults(fn=cmd_db_status)

    enrich = sub.add_parser(
        "enrich",
        help="Re-fetch detail pages for rows with no body or word_count < 200. "
             "Requires --backfill.",
    )
    enrich.add_argument("--backfill", action="store_true",
                        help="Backfill body text for rows below the scoring floor.")
    enrich.add_argument("--limit", type=int, default=100,
                        help="Max rows to backfill in this invocation (default 100).")
    enrich.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Log intent and rate-limit pacing but do not write to the DB.",
    )
    enrich.add_argument(
        "--source", type=str, default=None,
        help="Restrict to one scraper (e.g. linkedin, stepstone, xing). "
             "Rows from other sources are skipped and counted separately.",
    )
    enrich.set_defaults(fn=cmd_enrich_backfill)

    rescore = sub.add_parser(
        "rescore",
        help="Re-score jobs. With --backfill, tailored rescore for "
             "generated rows. With --base, scrub bogus legacy scores and "
             "rescore every row that now passes the precondition gate.",
    )
    rescore.add_argument(
        "--backfill", action="store_true",
        help="Run the tailored rescore against rows that are generated but "
             "missing score_tailored (jobs from before the rescorer was wired in).",
    )
    rescore.add_argument(
        "--base", action="store_true",
        help="Scrub legacy scores that violate the description_scraped/word-"
             "count precondition, then base-rescore every eligible row "
             "(PRD §7.5 FR-SCO-01..05).",
    )
    rescore.add_argument(
        "--limit", type=int, default=50,
        help="Max rows to rescore in this invocation (default 50).",
    )
    rescore.set_defaults(fn=cmd_rescore_backfill)

    profile = sub.add_parser("profile", help="Profile corpus + distillation commands.")
    profile_sub = profile.add_subparsers(dest="profile_cmd", required=True)
    profile_sub.add_parser("rebuild", help="Rebuild data/profile.compiled.yaml.").set_defaults(fn=cmd_profile_rebuild)
    profile_sub.add_parser("fetch-website", help="Refresh website corpus markdown files.").set_defaults(fn=cmd_profile_fetch_website)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
