"""Executive email report builder."""

from datetime import datetime, timezone


def build_report(audit: dict) -> tuple[str, str]:
    """Return (subject, body) for the post-run email."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    next_run = _next_run_date()

    subject = f"Drive Filing — {date}"

    total_organised = audit.get("moved", 0) + audit.get("renamed", 0)
    total_dupes = audit.get("trashed", 0)
    errors = audit.get("errors", 0)
    dry_run = audit.get("dry_run", False)
    time_saved = max(5, (total_organised * 2) + (total_dupes * 1))

    if dry_run:
        body = _dry_run_report(audit, date, next_run)
        subject = f"\U0001f534 APPROVAL NEEDED — {date}"
        return subject, body

    lines = []
    lines.append(f"DRIVE FILING COMPLETE — {date}")
    lines.append("━" * 38)
    lines.append(
        f"✅ {total_organised} files organised  •  "
        f"{total_dupes} duplicates removed  •  {errors} errors"
    )
    lines.append(f"Est. time saved: ~{time_saved} min")
    lines.append("")

    lines.append("WHAT WAS DONE")
    lines.append("─" * 13)

    for workstream, items in audit.get("by_workstream", {}).items():
        if items:
            summary = ", ".join(items[:3])
            if len(items) > 3:
                summary += f" (+{len(items) - 3} more)"
            lines.append(f"{workstream.capitalize():<10} {len(items)} filed: {summary}")

    if total_dupes:
        lines.append(f"{'Duplicates':<10} {total_dupes} trashed (recoverable for 30 days)")

    needs_review = audit.get("quarantined", [])
    if needs_review:
        lines.append("")
        lines.append("⚠️  ACTION NEEDED")
        lines.append("─" * 20)
        lines.append(f"_NeedsReview/ has {len(needs_review)} files waiting for your decision:")
        for item in needs_review:
            lines.append(f"  • {item['name']} — {item['reason']}")
        lines.append("Open Drive → _NeedsReview to review.")

    suggested = audit.get("suggested_rules", [])
    if suggested:
        lines.append("")
        lines.append("\U0001f4a1  SUGGESTED NEW RULES")
        lines.append("─" * 24)
        lines.append("These patterns appear regularly but have no rule yet:")
        for s in suggested:
            lines.append(f"  • \"{s['pattern']}\" — seen {s['count']}x, in {s['location']}")
        lines.append("Reply to this email or ask your filing agent to add them.")

    deferred = audit.get("deferred", {})
    imm = deferred.get("immigration", 0)
    recent = deferred.get("recent", 0)
    other = deferred.get("other", 0)
    if imm or recent or other:
        lines.append("")
        lines.append("⛔  DEFERRED (protected)")
        lines.append("─" * 24)
        if imm:
            lines.append(f"Immigration docs:  {imm} files — deferred to immigration workstream")
        if recent:
            lines.append(f"Recently modified: {recent} files — deferred (edited within 24h)")
        if other:
            lines.append(f"Other protected:   {other} files")

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    lines.append("")
    lines.append("\U0001f4cb  RECORDS")
    lines.append("─" * 11)
    lines.append(f"Audit log : filing-audit-{month}.txt  (Drive root)")
    lines.append(f"Rollback  : filing-rollback-{date}.json (Drive root — undo available)")
    lines.append(f"Next run  : {next_run}")
    lines.append("━" * 38)

    return subject, "\n".join(lines)


def _dry_run_report(audit: dict, date: str, next_run: str) -> str:
    planned = audit.get("planned_actions", 0)
    lines = [
        f"\U0001f534 APPROVAL NEEDED — {date}",
        "━" * 38,
        f"{planned} actions were planned but NOT executed (exceeds 50-action safety limit).",
        "Review the audit log, then re-run without --dry-run to confirm.",
        "",
        "PLANNED ACTIONS",
        "─" * 15,
    ]
    for action in audit.get("planned", [])[:20]:
        lines.append(f"  {action['type'].upper():<12} {action['name']}")
    if planned > 20:
        lines.append(f"  ... and {planned - 20} more (see audit log)")
    lines.append("")
    lines.append(f"Next scheduled run: {next_run}")
    lines.append("━" * 38)
    return "\n".join(lines)


def _next_run_date() -> str:
    today = datetime.now(timezone.utc)
    if today.day < 15:
        next_dt = today.replace(day=15)
    else:
        if today.month == 12:
            next_dt = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_dt = today.replace(month=today.month + 1, day=1)
    return next_dt.strftime("%Y-%m-%d")
