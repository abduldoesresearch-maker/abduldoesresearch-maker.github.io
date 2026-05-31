"""Claude agent loop — drives the filing process via Anthropic SDK tool use."""

import json
from datetime import datetime, timezone
from typing import Any

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from rules import FOLDER_IDS, SCAN_LOCATIONS, DEDUP_PATTERNS, RULES
from tools import ToolExecutor

console = Console()

SYSTEM_PROMPT = """You are an autonomous Google Drive filing agent. Your job is to:
1. Scan configured Drive locations for unorganised files
2. Classify each file against the filing rules
3. Apply all safety checks before executing anything
4. Move, rename, and trash files as needed
5. Quarantine ambiguous files that have been seen 2+ times
6. Send an executive summary report when done

## Filing rules summary
{rules_summary}

## Known folder IDs
{folder_ids}

## Scan locations
{scan_locations}

## Dedup patterns (global search, no time filter)
{dedup_patterns}

## Safety rules (apply in this order before ANY execution)
1. Volume guard: if total planned actions > 50, report planned actions and stop — do NOT execute
2. Age guard: skip files modified within the last 24 hours (deferred, not an error)
3. Protected: NEVER touch files/folders matching: Step Father, Halefom, EPP1-*, FD-258*, fd-1164*, Form 888*, lost passport*
4. Skip files already in their correct destination folder
5. Verify destination folder IDs exist before running each workstream
6. Log every action to rollback BEFORE executing it

## Process
- Load state (since timestamp, vendor cache, skipped patterns)
- Run parallel scans using the incremental since timestamp
- For Invoice-*.pdf and Receipt-*.pdf: use extract_pdf_vendor tool (checks cache first)
- For unmatched files: use flag_skipped_pattern; if count >= 2 use quarantine_file
- After all actions: send report to abduldoesresearch@gmail.com
- Keep tool calls focused and efficient — batch searches where possible
"""


def build_system_prompt() -> str:
    rules_summary = "\n".join(
        f"  - [{r.workstream}] {r.pattern} → {r.dest_parent_key}/{'/'.join(r.dest_subpath)}"
        for r in RULES
    )
    folder_ids = "\n".join(f"  {k}: {v}" for k, v in FOLDER_IDS.items())
    scan_locs = "\n".join(
        f"  - {loc['name']}" for loc in SCAN_LOCATIONS
    )
    dedup = ", ".join(DEDUP_PATTERNS)

    return SYSTEM_PROMPT.format(
        rules_summary=rules_summary,
        folder_ids=folder_ids,
        scan_locations=scan_locs,
        dedup_patterns=dedup,
    )


class DriveFilingAgent:
    def __init__(self, executor: ToolExecutor, dry_run: bool = False,
                 workstream: str = "all", since: str = None, send_email: bool = True):
        self.executor = executor
        self.dry_run = dry_run
        self.workstream = workstream
        self.since_override = since
        self.send_email = send_email
        self.client = anthropic.Anthropic()
        self.messages: list[dict] = []

    def run(self) -> dict:
        user_prompt = self._build_user_prompt()
        self.messages = [{"role": "user", "content": user_prompt}]

        console.print(Panel(
            f"[bold cyan]Drive Filing Agent[/bold cyan]\n"
            f"Mode: {'[yellow]DRY-RUN[/yellow]' if self.dry_run else '[green]LIVE[/green]'}  "
            f"Workstream: [cyan]{self.workstream}[/cyan]  "
            f"Since: [dim]{self.since_override or 'last run'}[/dim]",
            title="Starting"
        ))

        tool_defs = ToolExecutor.definitions()
        iteration = 0

        while True:
            iteration += 1
            with console.status(f"[cyan]Thinking... (iteration {iteration})[/cyan]"):
                response = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    system=build_system_prompt(),
                    tools=tool_defs,
                    messages=self.messages,
                )

            if response.stop_reason == "end_turn":
                final_text = next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )
                if final_text:
                    console.print(Panel(final_text, title="[green]Agent Complete[/green]"))
                break

            if response.stop_reason == "tool_use":
                self.messages.append({"role": "assistant", "content": response.content})
                tool_results = []

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    self._print_tool_call(block.name, block.input)
                    result = self.executor.execute(block.name, block.input)
                    self._print_tool_result(block.name, result)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })

                self.messages.append({"role": "user", "content": tool_results})

            else:
                console.print(f"[yellow]Unexpected stop reason: {response.stop_reason}[/yellow]")
                break

        return self.executor.audit

    def _build_user_prompt(self) -> str:
        lines = ["Run the Drive filing agent now."]
        if self.since_override:
            lines.append(f"Override scan window: only process files modified after {self.since_override}.")
        if self.workstream != "all":
            lines.append(f"Only process the {self.workstream} workstream.")
        if self.dry_run:
            lines.append("DRY-RUN MODE: classify and plan all actions but do NOT execute any moves, trashes, or folder creations.")
        if not self.send_email:
            lines.append("Skip sending the email report at the end.")
        return " ".join(lines)

    def _print_tool_call(self, name: str, inputs: dict) -> None:
        key_input = {k: v for k, v in inputs.items() if k not in ("content", "data")}
        console.print(
            Text("  ▶ ", style="cyan") +
            Text(name, style="bold cyan") +
            Text(f"  {json.dumps(key_input, default=str)[:120]}", style="dim")
        )

    def _print_tool_result(self, name: str, result: Any) -> None:
        if isinstance(result, dict) and "error" in result:
            console.print(Text(f"    ✗ ERROR: {result['error']}", style="red"))
        elif isinstance(result, list):
            console.print(Text(f"    ✓ {len(result)} items", style="green"))
        elif isinstance(result, dict) and result.get("status") == "dry_run":
            console.print(Text(f"    ○ dry-run (would execute)", style="yellow"))
        else:
            console.print(Text(f"    ✓ ok", style="green"))
