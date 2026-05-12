"""CLI entrypoint: `jobbot <command>`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
import shutil

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import REPO_ROOT, load_config, load_secrets
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


def cmd_scan_inbox(_args) -> int:
    from . import outcomes

    config = load_config()
    try:
        secrets = load_secrets()
    except KeyError as e:
        console.print(f"[yellow]missing inbox secret {e}; running DB-only scan[/yellow]")
        secrets = None
    with connect() as conn:
        summary = outcomes.scan_inbox(conn, secrets, config)
    console.print(f"inbox scan complete: {summary}")
    return 0


def cmd_init(_args) -> int:
    """Interactive newcomer wizard: writes .env + profile.yaml + config.yaml
    + base_cv.md after a focused Q&A. Designed for someone who has never
    touched the codebase."""
    from .onboard import run
    return run()


def cmd_apply(args) -> int:
    """Run the configured pipeline pass used by the scheduled apply job."""
    return cmd_run(args)


def cmd_mark_applied(args) -> int:
    """Mark a job as already applied to (outside the bot — LinkedIn UI,
    in-person, recruiter call). The pipeline's apply step will skip this
    job on every subsequent run."""
    from .state import mark_application_manually

    with connect() as conn:
        row = conn.execute(
            "SELECT id, title, company, status FROM seen_jobs WHERE id = ?",
            (args.job_id,),
        ).fetchone()
        if row is None:
            console.print(f"[red]no seen_jobs row found with id={args.job_id}[/red]")
            return 1
        mark_application_manually(conn, args.job_id, note=args.note,
                                  channel=args.channel)
    console.print(
        f"[green]marked as applied[/green]: {row['title']} @ {row['company']} "
        f"({args.job_id}) — future pipeline runs will skip this job."
    )
    if args.note:
        console.print(f"  note: {args.note}")
    return 0


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
    drain the queue without long-running pulls."""
    from .enrichment.runner import enrich_new_postings
    from .scoring import MIN_BODY_WORDS
    from .state import jobs_needing_backfill

    if not getattr(args, "backfill", False):
        console.print("[red]Usage:[/red] jobbot enrich --backfill [--limit N]")
        return 2

    cap = int(getattr(args, "limit", 100) or 100)
    with connect() as conn:
        candidates = jobs_needing_backfill(conn, min_words=MIN_BODY_WORDS, limit=cap)
        if not candidates:
            console.print("nothing to backfill — every row has body >= "
                          f"{MIN_BODY_WORDS} words.")
            return 0
        console.print(f"backfilling {len(candidates)} rows (cap {cap}, "
                      f"floor {MIN_BODY_WORDS} words)...")
        report = enrich_new_postings(candidates, conn, registry=REGISTRY)

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
    console.print(f"total: attempted={report.n_attempted}, "
                  f"succeeded={report.n_succeeded}, failed={report.n_failed}")
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
    Sonnet + the PRIMARY_ corpus CV. Costs ~1 LLM call per backfilled
    job.
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
    description-scraped + 100-word precondition, then re-score every row
    that now passes it (status in scraped / cannot_score:*, with a real
    body of >= 100 words) against Sonnet + the PRIMARY_ corpus CV.

    With `--force`, additionally null every existing base score first and
    re-evaluate every eligible row (used when the evaluator or CV source
    changed and historical scores no longer reflect reality). Late-stage
    rows (generated / apply_* / etc.) keep their pipeline status — only
    the score column is refreshed.

    Invoked via `jobbot rescore --base [--force]`. Bounded by --limit so a
    single invocation doesn't blow through the API budget on long-tail
    backlogs.
    """
    from .profile import load_profile
    from .scoring import CannotScore, llm_score
    from .state import (
        force_clear_base_scores, jobs_needing_base_rescore,
        jobs_needing_base_rescore_force, scrub_stale_scores,
        update_base_score_only, update_status,
    )
    from .models import JobStatus

    force = bool(getattr(args, "force", False))
    cap = int(getattr(args, "limit", 100) or 100)
    secrets = load_secrets()
    profile = load_profile()

    # Statuses where it's safe to overwrite `status` based on the new score.
    # For anything else (GENERATED, APPLY_*, etc.) we only refresh the
    # score column so we don't undo downstream pipeline progress.
    overwritable_statuses = {
        JobStatus.SCRAPED.value,
        JobStatus.SCORED.value,
        JobStatus.BELOW_THRESHOLD.value,
        JobStatus.CANNOT_SCORE_NO_BODY.value,
        JobStatus.CANNOT_SCORE_NO_PRIMARY_CV.value,
        JobStatus.CANNOT_SCORE_NO_BASE_CV.value,
        "cannot_score:no_primary_cv",
        "cannot_score:no_base_cv",
    }

    with connect() as conn:
        if force:
            early, late = force_clear_base_scores(conn)
            console.print(
                f"[yellow]force[/yellow] cleared {early} early-stage + "
                f"{late} late-stage score(s); late-stage statuses preserved"
            )

        n_scrubbed = scrub_stale_scores(conn)
        if n_scrubbed:
            console.print(
                f"[yellow]scrubbed[/yellow] {n_scrubbed} legacy score(s) "
                "that violated the description_scraped/word-count precondition"
            )
        elif not force:
            console.print("no stale scores to scrub")

        if force:
            candidates_with_status = jobs_needing_base_rescore_force(conn, limit=cap)
        else:
            candidates_with_status = [
                (job, JobStatus.SCRAPED.value)
                for job in jobs_needing_base_rescore(conn, limit=cap)
            ]
        if not candidates_with_status:
            console.print(
                "nothing to rescore — every eligible row already has a base score."
            )
            return 0

        console.print(
            f"rescoring {len(candidates_with_status)} row(s) with Sonnet + "
            f"PRIMARY_ CV — ~1 LLM call each (cap {cap})..."
        )

        table = Table(title="base rescore — Sonnet + PRIMARY_ CV")
        table.add_column("source"); table.add_column("title")
        table.add_column("score", justify="right")
        table.add_column("status", justify="right")

        n_ok = n_cannot = n_failed = n_score_only = 0
        for job, current_status in candidates_with_status:
            try:
                result = llm_score(job, profile, secrets, description_scraped=True)
            except CannotScore as e:
                reason = e.reason
                if reason.startswith("no_primary_cv"):
                    new_status = JobStatus.CANNOT_SCORE_NO_PRIMARY_CV
                elif reason.startswith("no_base_cv"):
                    new_status = JobStatus.CANNOT_SCORE_NO_BASE_CV
                else:
                    new_status = JobStatus.CANNOT_SCORE_NO_BODY
                # Never demote a late-stage row to cannot_score — refresh the
                # reason column but keep its pipeline status. Otherwise the
                # standard cannot_score downgrade is correct.
                if current_status in overwritable_statuses:
                    update_status(conn, job.id, new_status, score=None, reason=reason)
                    table.add_row(job.source, (job.title or "")[:50], "—", new_status.value)
                else:
                    update_base_score_only(conn, job.id, score=None, reason=reason)
                    table.add_row(job.source, (job.title or "")[:50], "—", current_status)
                n_cannot += 1
                continue
            except Exception as e:
                console.print(f"[red]fail[/red] {job.id}: {type(e).__name__}: {e}")
                n_failed += 1
                continue

            if current_status in overwritable_statuses:
                new_status = (
                    JobStatus.SCORED if result.score >= 70 else JobStatus.BELOW_THRESHOLD
                )
                update_status(conn, job.id, new_status,
                              score=result.score, reason=result.reason)
                table.add_row(
                    job.source, (job.title or "")[:50],
                    str(result.score), new_status.value,
                )
            else:
                update_base_score_only(conn, job.id, result.score, result.reason)
                n_score_only += 1
                table.add_row(
                    job.source, (job.title or "")[:50],
                    str(result.score), f"{current_status} (score refreshed)",
                )
            n_ok += 1

        console.print(table)
        summary = (
            f"done: {n_ok} scored ({n_score_only} score-only refresh), "
            f"{n_cannot} cannot_score, {n_failed} failed"
        )
        console.print(summary)
    return 0 if n_failed == 0 else 1


def cmd_profile_rebuild(_args) -> int:
    """PRD §7.4 FR-PRO-02: rebuild data/profile.compiled.yaml from corpus."""
    output = rebuild_compiled_profile(secrets=load_secrets())
    console.print(f"compiled profile written: {output}")
    return 0


def cmd_profile_fetch_website(_args) -> int:
    """PRD §7.4 FR-PRO-05: crawl true-north.berlin into website corpus."""
    count = fetch_website()
    console.print(f"website corpus refreshed: {count} pages")
    return 0


def _corpus_dir(kind: str) -> Path:
    if kind not in {"cvs", "cover_letters", "website"}:
        raise ValueError(f"unsupported profile corpus kind: {kind}")
    return REPO_ROOT / "data" / "corpus" / kind


def cmd_profile_add(args) -> int:
    """Copy a local profile artifact into data/corpus."""
    src = Path(args.path).expanduser()
    if not src.is_file():
        console.print(f"[red]missing profile artifact:[/red] {src}")
        return 1
    dest_dir = _corpus_dir(args.kind)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_name = src.name
    if args.primary and not dest_name.startswith("PRIMARY_"):
        dest_name = f"PRIMARY_{dest_name}"
    dest = dest_dir / dest_name
    if dest.exists() and not args.force:
        console.print(
            f"[red]destination exists:[/red] {dest} "
            "(pass --force to replace it)"
        )
        return 1
    shutil.copy2(src, dest)
    console.print(f"profile artifact added: {dest}")
    return 0


def cmd_profile_remove(args) -> int:
    """Remove a profile artifact from data/corpus by path or basename."""
    raw = Path(args.path).expanduser()
    corpus_root = (REPO_ROOT / "data" / "corpus").resolve()
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append((REPO_ROOT / raw).resolve())
        candidates.extend(corpus_root.rglob(raw.name))

    for candidate in candidates:
        target = candidate.resolve()
        try:
            target.relative_to(corpus_root)
        except ValueError:
            continue
        if target.is_file():
            target.unlink()
            console.print(f"profile artifact removed: {target}")
            return 0

    console.print(f"[yellow]profile artifact not found:[/yellow] {args.path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jobbot")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init",    help="Interactive newcomer setup: writes .env + profile.yaml + config.yaml + base_cv.md.").set_defaults(fn=cmd_init)
    sub.add_parser("run",     help="Run one full pipeline pass.").set_defaults(fn=cmd_run)
    sub.add_parser("digest",  help="Send a digest of the last 24h.").set_defaults(fn=cmd_digest)
    sub.add_parser("status",  help="Show pipeline counts.").set_defaults(fn=cmd_status)
    sub.add_parser("sources", help="List registered scrapers.").set_defaults(fn=cmd_sources)
    sub.add_parser("dashboard", help="Start web dashboard on localhost:5001.").set_defaults(fn=cmd_dashboard)
    sub.add_parser("db-status", help="Show SQLite writer-lock state and any holders.").set_defaults(fn=cmd_db_status)
    sub.add_parser("scan-inbox", help="Scan inbox for application outcomes.").set_defaults(fn=cmd_scan_inbox)
    sub.add_parser("inbox-scan", help="Alias for scan-inbox.").set_defaults(fn=cmd_scan_inbox)
    sub.add_parser("apply", help="Run the scheduled apply pipeline pass.").set_defaults(fn=cmd_apply)

    mark = sub.add_parser(
        "mark-applied",
        help="Mark a job as already applied to outside the bot. Future "
             "pipeline runs will skip it.",
    )
    mark.add_argument("job_id", help="The seen_jobs.id of the job to mark.")
    mark.add_argument("--note", default=None,
                      help="Free-text note (e.g. 'applied via LinkedIn UI').")
    mark.add_argument("--channel", default="manual",
                      help="Provenance tag for proof_evidence (default: manual).")
    mark.set_defaults(fn=cmd_mark_applied)

    enrich = sub.add_parser(
        "enrich",
        help="Re-fetch detail pages for rows with no body or word_count < 100. "
             "Requires --backfill.",
    )
    enrich.add_argument("--backfill", action="store_true",
                        help="Backfill body text for rows below the scoring floor.")
    enrich.add_argument("--limit", type=int, default=100,
                        help="Max rows to backfill in this invocation (default 100).")
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
    rescore.add_argument(
        "--force", action="store_true",
        help="With --base, null every existing base score first and "
             "re-evaluate every eligible row against Sonnet + the current "
             "CV. Used after the evaluator or CV source changes. SCORED/"
             "BELOW_THRESHOLD rows fall back to SCRAPED; later-stage rows "
             "(generated, apply_*, etc.) keep their status — only the score "
             "is refreshed.",
    )
    rescore.set_defaults(fn=cmd_rescore_backfill)

    profile = sub.add_parser("profile", help="Profile corpus + distillation commands.")
    profile_sub = profile.add_subparsers(dest="profile_cmd", required=True)
    profile_sub.add_parser("rebuild", help="Rebuild data/profile.compiled.yaml.").set_defaults(fn=cmd_profile_rebuild)
    profile_sub.add_parser("fetch-website", help="Refresh website corpus markdown files.").set_defaults(fn=cmd_profile_fetch_website)
    profile_add = profile_sub.add_parser("add", help="Add a CV/profile artifact to data/corpus.")
    profile_add.add_argument("path", help="File to copy into the corpus.")
    profile_add.add_argument(
        "--kind", choices=["cvs", "cover_letters", "website"], default="cvs",
        help="Corpus bucket to copy into (default: cvs).",
    )
    profile_add.add_argument(
        "--primary", action="store_true",
        help="Prefix the copied file with PRIMARY_ for the main CV.",
    )
    profile_add.add_argument(
        "--force", action="store_true",
        help="Replace an existing corpus file with the same name.",
    )
    profile_add.set_defaults(fn=cmd_profile_add)

    profile_remove = profile_sub.add_parser("remove", help="Remove a profile artifact from data/corpus.")
    profile_remove.add_argument("path", help="Corpus path or basename to remove.")
    profile_remove.set_defaults(fn=cmd_profile_remove)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
