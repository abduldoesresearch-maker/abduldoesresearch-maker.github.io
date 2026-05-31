"""Persistent state management — reads and writes state files in Drive root."""

import json
from datetime import datetime, timezone
from typing import Optional
from drive_client import DriveClient


class StateManager:
    def __init__(self, drive: DriveClient):
        self.drive = drive
        self._ids: dict = {}
        self._data: dict = {}

    def load(self) -> dict:
        """Load all state files from Drive root in one pass."""
        files = ["filing-last-run.txt", "filing-vendor-cache.json", "filing-skipped-patterns.json"]

        for filename in files:
            fid = self.drive.find_in_root(filename)
            self._ids[filename] = fid

            if fid:
                try:
                    content = self.drive.read_content(fid).decode("utf-8").strip()
                    if filename.endswith(".json"):
                        self._data[filename] = json.loads(content)
                    else:
                        self._data[filename] = content
                except Exception:
                    self._data[filename] = {} if filename.endswith(".json") else None
            else:
                self._data[filename] = {} if filename.endswith(".json") else None

        return {
            "since": self._data.get("filing-last-run.txt") or "2020-01-01T00:00:00Z",
            "vendor_cache": self._data.get("filing-vendor-cache.json", {}),
            "skipped_patterns": self._data.get("filing-skipped-patterns.json", {}),
        }

    def save(self, vendor_cache: dict, skipped_patterns: dict,
             rollback: list, run_date: Optional[str] = None) -> None:
        """Write all state files back to Drive root."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        self.drive.upload_text(
            "filing-last-run.txt",
            now,
            self._ids.get("filing-last-run.txt"),
        )
        self.drive.upload_text(
            "filing-vendor-cache.json",
            json.dumps(vendor_cache, indent=2),
            self._ids.get("filing-vendor-cache.json"),
        )
        self.drive.upload_text(
            "filing-skipped-patterns.json",
            json.dumps(skipped_patterns, indent=2),
            self._ids.get("filing-skipped-patterns.json"),
        )
        self.drive.upload_text(
            f"filing-rollback-{date}.json",
            json.dumps(rollback, indent=2),
            self._ids.get(f"filing-rollback-{date}.json"),
        )

    def append_audit_log(self, entry: str) -> None:
        """Append a run block to the current month's audit log."""
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        filename = f"filing-audit-{month}.txt"
        fid = self.drive.find_in_root(filename)

        existing = ""
        if fid:
            try:
                existing = self.drive.read_content(fid).decode("utf-8")
            except Exception:
                existing = ""

        self.drive.upload_text(filename, existing + "\n" + entry, fid)
