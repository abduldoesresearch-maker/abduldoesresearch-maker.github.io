# Case Study: Autonomous AI Document Filing Agent

**Type:** Agentic AI System / Workflow Automation  
**Stack:** Claude Sonnet 4.6 · Claude Haiku 4.5 · Google Drive API · Gmail API · OAuth 2.0  
**Outcome:** Fully autonomous bi-weekly Drive organisation with zero manual intervention

---

## The Problem

A personal Drive with 5 years of mixed documents had become unmanageable:

- **250+ files** across 5 workstreams (finance, immigration, learning, personal, family) with no consistent structure
- **Duplicate files everywhere** — 4 copies of the same bank export, 3 copies of the same invoice
- **Zero naming convention** — invoices with no date or vendor, datasets with hashed filenames
- **No audit trail** — no way to know what was where or when it was moved
- **Time cost** — estimated 2–3 hours per month of manual search and reorganisation

The client needed this solved permanently, not patched. A one-time script would break the moment a filename changed. A rules-based macro would require manual maintenance. The solution had to be intelligent, self-maintaining, and safe enough to run without supervision.

---

## The Solution

An autonomous Claude-powered agent that:
1. Connects to Google Drive via OAuth
2. Scans for new and unorganised files every 2 weeks
3. Classifies files using AI and pattern rules
4. Executes moves, renames, and deduplication
5. Emails an executive summary report
6. Runs forever — no human input required

---

## Architecture

```
Scheduler (bi-weekly cron)
    │
    ▼
Phase 1: Bootstrap
    Load OAuth token → refresh access token
    Initialise helpers (Drive API, Gmail API)
    │
    ▼
Phase 2: Load state (parallel)
    ├── filing-last-run.txt       (incremental scan anchor)
    ├── filing-vendor-cache.json  (AI extraction cache)
    ├── filing-skipped-patterns.json (quarantine tracker)
    └── filing-rollback-{date}.json  (undo log)
    │
    ▼
Phase 3: Parallel scan (8 folders simultaneously)
    Incremental filter: modifiedTime > last run
    + Targeted dedup search across known-duplicate patterns
    │
    ▼
Phase 4: Classify each file
    ├── Pattern rules (finance, learning, legal)
    └── Subagents for ambiguous files:
        ├── PDF Vendor Subagent (Claude Haiku)
        │   → reads invoice/receipt, returns {vendor, date}
        └── Unknown File Subagent (Claude Haiku)
            → categorises by metadata, confidence threshold 0.85
    │
    ▼
Phase 5: Safety check (all 4 must pass before execution)
    ├── Volume guard:    > 50 actions → dry-run, email for approval
    ├── Age guard:       modified < 24h → defer
    ├── Pre-flight:      destination folder IDs verified live
    └── Protected list:  immigration docs, named individuals → never touch
    │
    ▼
Phase 6: Execute
    Move + rename (atomic Drive API call)
    Soft delete → Trash (30-day recovery, never permanent)
    Quarantine → _NeedsReview/ (files unrecognised 2+ runs)
    Log every action to rollback before executing
    │
    ▼
Phase 7: Save state (parallel)
    Update all 4 state files
    Append to monthly audit log
    │
    ▼
Phase 8: Executive email report
    Gmail API send
    Clean sectioned format
    Optional sections hidden when empty
```

---

## Key Engineering Decisions

### Incremental scanning
Rather than re-scanning the entire Drive every run, the agent stores a timestamp after each run and queries the Drive API with `modifiedTime > {SINCE}`. On a typical run after 2 weeks, this reduces files scanned from 250+ to under 20. Deduplication runs a separate targeted query against known-duplicate filename patterns so older duplicates aren't missed.

### Stateful subagents
PDF invoices and receipts cannot be classified by filename alone. Rather than reading every PDF every run, the agent spawns a Claude Haiku subagent on the first encounter — passing the PDF as base64, receiving `{vendor, date}` as structured JSON — and caches the result. Subsequent runs use the cache. This eliminates redundant API calls and keeps the run fast as the vendor pool grows.

### Quarantine over guess
When a file doesn't match any rule, the agent doesn't guess. It tracks the pattern in `filing-skipped-patterns.json`. After 2 consecutive runs of seeing the same pattern unmatched, it moves the file to `_NeedsReview/` and flags it in the email report. This surfaces genuine ambiguity to the user without polluting the folder structure with misfiled documents.

### Soft-delete safety contract
All duplicate deletion is via `PATCH /files/{id}` with `{"trashed": true}` — never `DELETE`. Drive Trash provides a 30-day recovery window on everything the agent touches. Combined with the per-run rollback JSON, no action is irreversible.

### Volume guard
A runaway agent is a liability. Before executing any actions, the agent counts the total planned operations. If it exceeds 50, it switches to dry-run mode — logging what it would do but executing nothing — and emails the client for explicit approval. This caps the blast radius of any misconfiguration.

---

## Results

**Initial run (first-time full scan of 250 files):**

| Metric | Result |
|---|---|
| Files moved and organised | 34 |
| Exact duplicates removed | 14 |
| Orphaned shortcuts deleted | 7 |
| New folders created | 11 |
| Errors | 0 |
| Files correctly deferred (immigration, protected) | 9 |
| Estimated time saved | ~90 min |

**Subsequent runs (incremental, bi-weekly):**

| Metric | Typical result |
|---|---|
| Files scanned | 8–20 (vs 250+ full scan) |
| Files actioned | 3–12 |
| Run time | ~2 min |
| Errors | 0 |

**Cumulative outcomes after 3 runs:**
- Drive root cleared from 21 unorganised files to 0
- Vendor cache built: 5 vendors identified, no PDF re-reads since
- `filing-skipped-patterns.json` seeded: 3 patterns flagged for rule suggestions
- Monthly audit log maintained: full searchable history of every action

---

## Safety Record

Across all test and production runs:
- **0 files permanently deleted** — all removals via Trash
- **0 protected files touched** — immigration docs, named individuals, active files all correctly deferred
- **0 miscategorised files** — quarantine threshold prevented any guessed moves
- **1 rollback file per run** — complete undo available for every execution

---

## Delivered Artefacts

| Artefact | Description |
|---|---|
| Scheduled routine | Bi-weekly remote agent, `0 0 1,15 * *` cron |
| `drive-helper.ps1` | PowerShell wrapper for Drive REST API (move/rename/delete/search/create) |
| `verify-agent.ps1` | Health check script — verifies token scopes, folder IDs, state files in one command |
| State files in Drive | `filing-last-run.txt`, `filing-vendor-cache.json`, `filing-skipped-patterns.json` |
| Per-run rollback JSON | Complete undo log for every execution |
| Monthly audit log | Append-only record of all actions |
| Executive email report | Post-run summary with suggested rules, quarantine alerts, and records |

---

## What This Demonstrates

| Capability | How it's demonstrated |
|---|---|
| Agentic system design | 8-phase pipeline with clear separation of concerns |
| Multi-model orchestration | Sonnet for reasoning, Haiku subagents for fast classification |
| Stateful agent memory | Persistent state files enable incremental, self-improving behaviour |
| Production safety patterns | Volume guard, age guard, pre-flight checks, soft delete, rollback |
| API integration | Google Drive v3 and Gmail v1 REST APIs, OAuth 2.0 |
| Autonomous scheduling | Claude Code remote agent infrastructure, cron-based |
| Zero-intervention operation | Client receives email report; never logs in to manage the agent |

---

## Replicability

This agent is fully parameterised. Deploying for a new client requires:

1. A Google Cloud project (~10 min setup)
2. One-time OAuth browser authentication
3. A filing rules configuration tailored to the client's document types and folder structure
4. Registration of the scheduled routine

The core infrastructure — incremental scanning, vendor cache, safety checks, rollback logging, executive reporting, subagent classification — is reusable as-is.

**Ideal clients:** Freelancers, consultants, small teams, or anyone managing a large shared Google Drive who wants it organised automatically without a SaaS subscription or ongoing maintenance overhead.

---

*Built and deployed end-to-end in a single session using Claude Code.*
