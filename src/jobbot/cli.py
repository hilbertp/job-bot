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
from .scrapers import REGISTRY
from .state import connect

console = Console()


def cmd_run(_args) -> int:
    result = run_with_failure_alerts(load_config(), load_secrets())
    
    # Build workflow progress display
    fetched = result.get("n_fetched", 0)
    new = result.get("n_new", 0)
    generated = result.get("n_generated", 0)
    applied = result.get("n_applied", 0)
    errors = result.get("n_errors", 0)
    
    progress = (
        f"[cyan]Scraped[/cyan] {fetched} jobs, {new} new\n"
        f"[yellow]Tailored[/yellow] {generated} CVs + cover letters\n"
        f"[green]Applied[/green] {applied} applications"
    )
    if errors:
        progress += f"\n[red]Errors[/red] {errors}"
    
    console.print(Panel(progress, title="[bold]jobbot · workflow progress[/bold]", border_style="blue"))
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jobbot")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run",     help="Run one full pipeline pass.").set_defaults(fn=cmd_run)
    sub.add_parser("digest",  help="Send a digest of the last 24h.").set_defaults(fn=cmd_digest)
    sub.add_parser("status",  help="Show pipeline counts.").set_defaults(fn=cmd_status)
    sub.add_parser("sources", help="List registered scrapers.").set_defaults(fn=cmd_sources)
    sub.add_parser("dashboard", help="Start web dashboard on localhost:5001.").set_defaults(fn=cmd_dashboard)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
