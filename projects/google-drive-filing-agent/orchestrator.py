"""
google-drive-filing-agent
─────────────────────────
Autonomous Google Drive organiser powered by Claude.

Usage:
  python orchestrator.py                          # full run
  python orchestrator.py --dry-run                # preview only
  python orchestrator.py --workstream finance     # one workstream
  python orchestrator.py --since 2026-06-01       # override scan window
  python orchestrator.py --no-email               # skip email report
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv()

from auth import get_access_token
from drive_client import DriveClient
from gmail_client import GmailClient
from state import StateManager
from tools import ToolExecutor
from agent import DriveFilingAgent
from report import build_report

console = Console()


def check_env() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key.[/red]")
        sys.exit(1)


def print_summary(audit: dict, dry_run: bool) -> None:
    table = Table(title="Run Summary", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Count", justify="right")

    table.add_row("Files moved",           str(audit.get("moved", 0)))
    table.add_row("Files renamed",         str(audit.get("renamed", 0)))
    table.add_row("Duplicates trashed",    str(audit.get("trashed", 0)))
    table.add_row("Quarantined",           str(len(audit.get("quarantined", []))))
    table.add_row("Errors",                str(audit.get("errors", 0)))

    if dry_run:
        table.add_row("Planned (not executed)", str(audit.get("planned_actions", 0)))

    console.print(table)

    if audit.get("quarantined"):
        console.print("\n[yellow]⚠  Files sent to _NeedsReview/:[/yellow]")
        for item in audit["quarantined"]:
            console.print(f"   • {item['name']} — {item['reason']}")

    if audit.get("suggested_rules"):
        console.print("\n[cyan]💡  Suggested new rules:[/cyan]")
        for s in audit["suggested_rules"]:
            console.print(f'   • "{s["pattern"]}" — seen {s["count"]}x in {s["location"]}')


@click.command()
@click.option("--dry-run",    is_flag=True,  help="Preview actions without executing anything")
@click.option("--workstream", default="all", type=click.Choice(["all", "finance", "learning", "legal"]),
              help="Limit run to one workstream")
@click.option("--since",      default=None,  help="Override scan window (ISO 8601 timestamp)")
@click.option("--no-email",   is_flag=True,  help="Skip sending the email report")
@click.option("--verbose",    is_flag=True,  help="Print full tool results")
def main(dry_run: bool, workstream: str, since: str, no_email: bool, verbose: bool) -> None:
    """Autonomous Google Drive filing agent powered by Claude."""

    check_env()

    # ── Authenticate ──────────────────────────────────────────────────────────
    with console.status("[cyan]Authenticating with Google...[/cyan]"):
        try:
            token = get_access_token()
        except Exception as e:
            console.print(f"[red]Auth failed: {e}[/red]")
            sys.exit(1)

    drive  = DriveClient(token)
    gmail  = GmailClient(token)

    # ── Load state ────────────────────────────────────────────────────────────
    with console.status("[cyan]Loading state from Drive...[/cyan]"):
        state_mgr = StateManager(drive)
        state = state_mgr.load()

    if since:
        state["since"] = since
        console.print(f"[dim]Scan window overridden: files after {since}[/dim]")
    else:
        console.print(f"[dim]Scanning files modified after: {state['since']}[/dim]")

    # ── Run agent ─────────────────────────────────────────────────────────────
    executor = ToolExecutor(drive, gmail, state, dry_run=dry_run)
    agent    = DriveFilingAgent(
        executor,
        dry_run=dry_run,
        workstream=workstream,
        since=since,
        send_email=not no_email,
    )

    audit = agent.run()

    # ── Save state ────────────────────────────────────────────────────────────
    if not dry_run:
        with console.status("[cyan]Saving state to Drive...[/cyan]"):
            state_mgr.save(
                vendor_cache=state.get("vendor_cache", {}),
                skipped_patterns=state.get("skipped_patterns", {}),
                rollback=executor.rollback,
            )

        # Append to monthly audit log
        run_block = _build_audit_block(audit)
        state_mgr.append_audit_log(run_block)
        console.print("[dim]State and audit log saved.[/dim]")

    # ── Print summary ─────────────────────────────────────────────────────────
    print_summary(audit, dry_run)

    if dry_run:
        console.print(Panel(
            "[yellow]Dry-run complete. No changes were made.[/yellow]\n"
            "Run without --dry-run to execute.",
            title="Dry-Run"
        ))
    else:
        console.print(Panel("[green]Run complete.[/green]", title="Done"))


def _build_audit_block(audit: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"=== Run: {now} ===",
        f"Moved:      {audit.get('moved', 0)}",
        f"Renamed:    {audit.get('renamed', 0)}",
        f"Trashed:    {audit.get('trashed', 0)}",
        f"Quarantined:{len(audit.get('quarantined', []))}",
        f"Errors:     {audit.get('errors', 0)}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
