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
from .state import connect

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


def cmd_dashboard(_args) -> int:
    from .dashboard import run as run_dashboard
    console.print("[bold]🤖 jobbot dashboard[/bold] starting on [cyan]http://localhost:5001[/cyan]")
    console.print("Press Ctrl+C to stop")
    run_dashboard()
    return 0


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

    profile = sub.add_parser("profile", help="Profile corpus + distillation commands.")
    profile_sub = profile.add_subparsers(dest="profile_cmd", required=True)
    profile_sub.add_parser("rebuild", help="Rebuild data/profile.compiled.yaml.").set_defaults(fn=cmd_profile_rebuild)
    profile_sub.add_parser("fetch-website", help="Refresh website corpus markdown files.").set_defaults(fn=cmd_profile_fetch_website)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
