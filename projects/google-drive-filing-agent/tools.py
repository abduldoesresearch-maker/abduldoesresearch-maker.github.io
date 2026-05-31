"""Tool implementations — called by the Claude agent via Anthropic SDK tool use."""

import json
import re
from datetime import datetime, timezone
from typing import Any

import anthropic

from drive_client import DriveClient
from gmail_client import GmailClient
from rules import FOLDER_IDS, is_protected, match_rule


class ToolExecutor:
    def __init__(self, drive: DriveClient, gmail: GmailClient,
                 state: dict, dry_run: bool = False):
        self.drive = drive
        self.gmail = gmail
        self.state = state
        self.dry_run = dry_run
        self.rollback: list[dict] = []
        self.audit: dict = {
            "moved": 0, "renamed": 0, "trashed": 0, "errors": 0,
            "quarantined": [], "deferred": {"immigration": 0, "recent": 0, "other": 0},
            "suggested_rules": [], "by_workstream": {},
            "dry_run": dry_run, "planned": [], "planned_actions": 0,
        }
        self._anthropic = anthropic.Anthropic()

    # ── Tool definitions for Anthropic SDK ───────────────────────────────────

    @staticmethod
    def definitions() -> list[dict]:
        return [
            {
                "name": "search_drive",
                "description": "Search Google Drive for files matching a query string",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Drive API query (e.g. \"'root' in parents and trashed=false\")"},
                        "page_size": {"type": "integer", "default": 200},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_file_metadata",
                "description": "Get metadata for a specific file by ID",
                "input_schema": {
                    "type": "object",
                    "properties": {"file_id": {"type": "string"}},
                    "required": ["file_id"],
                },
            },
            {
                "name": "move_file",
                "description": "Move a file to a new parent folder, optionally renaming it",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string"},
                        "add_parent": {"type": "string", "description": "Destination folder ID"},
                        "remove_parent": {"type": "string", "description": "Current parent folder ID"},
                        "new_name": {"type": "string", "description": "New filename (optional)"},
                    },
                    "required": ["file_id", "add_parent", "remove_parent"],
                },
            },
            {
                "name": "trash_file",
                "description": "Move a file to Drive Trash (soft delete, 30-day recovery)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string"},
                        "reason": {"type": "string", "description": "Why this file is being trashed"},
                    },
                    "required": ["file_id", "reason"],
                },
            },
            {
                "name": "create_folder",
                "description": "Create a subfolder inside a parent folder",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "parent_id": {"type": "string"},
                    },
                    "required": ["name", "parent_id"],
                },
            },
            {
                "name": "get_or_create_folder",
                "description": "Return existing folder ID or create it",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "parent_id": {"type": "string"},
                    },
                    "required": ["name", "parent_id"],
                },
            },
            {
                "name": "extract_pdf_vendor",
                "description": "Read a PDF invoice/receipt and extract vendor name and date using AI",
                "input_schema": {
                    "type": "object",
                    "properties": {"file_id": {"type": "string"}},
                    "required": ["file_id"],
                },
            },
            {
                "name": "get_state",
                "description": "Get current agent state: last run timestamp, vendor cache, skipped patterns",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "update_vendor_cache",
                "description": "Add a vendor mapping to the cache",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename_stem": {"type": "string"},
                        "vendor": {"type": "string"},
                        "date": {"type": "string"},
                    },
                    "required": ["filename_stem", "vendor"],
                },
            },
            {
                "name": "flag_skipped_pattern",
                "description": "Record that a file pattern was skipped this run",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "filename": {"type": "string"},
                        "location": {"type": "string"},
                    },
                    "required": ["pattern", "filename", "location"],
                },
            },
            {
                "name": "quarantine_file",
                "description": "Move an ambiguous file to _NeedsReview/ folder",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string"},
                        "filename": {"type": "string"},
                        "current_parent": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["file_id", "filename", "current_parent", "reason"],
                },
            },
            {
                "name": "get_folder_id",
                "description": "Look up a known folder ID by key name",
                "input_schema": {
                    "type": "object",
                    "properties": {"key": {"type": "string", "description": "Key from FOLDER_IDS dict"}},
                    "required": ["key"],
                },
            },
            {
                "name": "send_report",
                "description": "Send the executive email report",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["to", "subject", "body"],
                },
            },
            {
                "name": "log_workstream_action",
                "description": "Record a completed action for the audit summary",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "workstream": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["workstream", "description"],
                },
            },
        ]

    # ── Dispatcher ────────────────────────────────────────────────────────────

    def execute(self, name: str, inputs: dict) -> Any:
        dispatch = {
            "search_drive":         self._search_drive,
            "get_file_metadata":    self._get_file_metadata,
            "move_file":            self._move_file,
            "trash_file":           self._trash_file,
            "create_folder":        self._create_folder,
            "get_or_create_folder": self._get_or_create_folder,
            "extract_pdf_vendor":   self._extract_pdf_vendor,
            "get_state":            self._get_state,
            "update_vendor_cache":  self._update_vendor_cache,
            "flag_skipped_pattern": self._flag_skipped_pattern,
            "quarantine_file":      self._quarantine_file,
            "get_folder_id":        self._get_folder_id,
            "send_report":          self._send_report,
            "log_workstream_action":self._log_workstream_action,
        }
        fn = dispatch.get(name)
        if not fn:
            return {"error": f"Unknown tool: {name}"}
        try:
            return fn(**inputs)
        except Exception as e:
            self.audit["errors"] += 1
            return {"error": str(e)}

    # ── Tool implementations ──────────────────────────────────────────────────

    def _search_drive(self, query: str, page_size: int = 200) -> list:
        return self.drive.search(query, page_size)

    def _get_file_metadata(self, file_id: str) -> dict:
        return self.drive.get_metadata(file_id)

    def _move_file(self, file_id: str, add_parent: str,
                   remove_parent: str, new_name: str = None) -> dict:
        self.rollback.append({
            "action": "move", "file_id": file_id,
            "from_parent": remove_parent, "to_parent": add_parent,
            "renamed_to": new_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if self.dry_run:
            action = {"type": "move", "file_id": file_id, "name": new_name or file_id}
            self.audit["planned"].append(action)
            self.audit["planned_actions"] += 1
            return {"status": "dry_run", "would_move_to": add_parent}

        result = self.drive.move(file_id, add_parent, remove_parent, new_name)
        if new_name:
            self.audit["renamed"] += 1
        else:
            self.audit["moved"] += 1
        return result

    def _trash_file(self, file_id: str, reason: str = "") -> dict:
        self.rollback.append({
            "action": "trash", "file_id": file_id, "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if self.dry_run:
            self.audit["planned"].append({"type": "trash", "file_id": file_id, "name": reason})
            self.audit["planned_actions"] += 1
            return {"status": "dry_run"}

        result = self.drive.trash(file_id)
        self.audit["trashed"] += 1
        return result

    def _create_folder(self, name: str, parent_id: str) -> dict:
        if self.dry_run:
            return {"status": "dry_run", "name": name}
        folder_id = self.drive.create_folder(name, parent_id)
        return {"id": folder_id, "name": name}

    def _get_or_create_folder(self, name: str, parent_id: str) -> dict:
        if self.dry_run:
            return {"status": "dry_run", "name": name}
        folder_id = self.drive.get_or_create_folder(name, parent_id)
        return {"id": folder_id, "name": name}

    def _extract_pdf_vendor(self, file_id: str) -> dict:
        vendor_cache = self.state.get("vendor_cache", {})
        if file_id in vendor_cache:
            return vendor_cache[file_id]

        pdf_b64 = self.drive.read_pdf_as_base64(file_id)

        response = self._anthropic.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract the vendor/company name and invoice or receipt date from this document. "
                            "Reply ONLY as JSON: {\"vendor\": \"VendorName\", \"date\": \"YYYY-MM-DD\"}. "
                            "If unclear: vendor=\"Unknown\", date=\"0000-00-00\"."
                        ),
                    },
                ],
            }],
        )

        try:
            result = json.loads(response.content[0].text)
        except Exception:
            result = {"vendor": "Unknown", "date": "0000-00-00"}

        vendor_cache[file_id] = result
        self.state["vendor_cache"] = vendor_cache
        return result

    def _get_state(self) -> dict:
        return self.state

    def _update_vendor_cache(self, filename_stem: str, vendor: str, date: str = "") -> dict:
        self.state.setdefault("vendor_cache", {})[filename_stem] = {
            "vendor": vendor, "date": date
        }
        return {"status": "ok"}

    def _flag_skipped_pattern(self, pattern: str, filename: str, location: str) -> dict:
        patterns = self.state.setdefault("skipped_patterns", {})
        if pattern not in patterns:
            patterns[pattern] = {"count": 0, "filenames": [], "location": location}
        patterns[pattern]["count"] += 1
        if filename not in patterns[pattern]["filenames"]:
            patterns[pattern]["filenames"].append(filename)

        if patterns[pattern]["count"] >= 2:
            self.audit["suggested_rules"].append({
                "pattern": pattern,
                "count": patterns[pattern]["count"],
                "location": location,
            })
        return {"count": patterns[pattern]["count"]}

    def _quarantine_file(self, file_id: str, filename: str,
                         current_parent: str, reason: str) -> dict:
        review_id = self.drive.get_or_create_folder("_NeedsReview", "root")
        self.rollback.append({
            "action": "quarantine", "file_id": file_id,
            "from_parent": current_parent, "to_parent": review_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if self.dry_run:
            self.audit["planned"].append({"type": "quarantine", "file_id": file_id, "name": filename})
            self.audit["planned_actions"] += 1
        else:
            self.drive.move(file_id, review_id, current_parent)

        self.audit["quarantined"].append({"name": filename, "reason": reason})
        return {"status": "quarantined", "folder": "_NeedsReview"}

    def _get_folder_id(self, key: str) -> dict:
        fid = FOLDER_IDS.get(key)
        if not fid:
            return {"error": f"Unknown folder key: {key}. Available: {list(FOLDER_IDS.keys())}"}
        return {"id": fid, "key": key}

    def _send_report(self, to: str, subject: str, body: str) -> dict:
        if self.dry_run:
            return {"status": "dry_run_skipped"}
        self.gmail.send(to, subject, body)
        return {"status": "sent"}

    def _log_workstream_action(self, workstream: str, description: str) -> dict:
        self.audit["by_workstream"].setdefault(workstream, []).append(description)
        return {"status": "logged"}
