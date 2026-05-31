"""Google Drive REST API v3 wrapper."""

import base64
from typing import Optional
import requests


DRIVE_BASE = "https://www.googleapis.com/drive/v3"
FILE_FIELDS = "id,name,mimeType,size,createdTime,modifiedTime,parents"


class DriveClient:
    def __init__(self, access_token: str):
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def _get(self, path: str, params: dict = None) -> dict:
        resp = requests.get(f"{DRIVE_BASE}{path}", headers=self.headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, params: dict = None, body: dict = None) -> dict:
        resp = requests.patch(
            f"{DRIVE_BASE}{path}",
            headers=self.headers,
            params=params,
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def _post(self, path: str, body: dict) -> dict:
        resp = requests.post(f"{DRIVE_BASE}{path}", headers=self.headers, json=body, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: str, page_size: int = 200) -> list[dict]:
        """Return files matching a Drive API query string."""
        result = self._get("/files", params={
            "q": query,
            "fields": f"files({FILE_FIELDS})",
            "pageSize": page_size,
        })
        return result.get("files", [])

    def list_folder(self, folder_id: str, since: Optional[str] = None) -> list[dict]:
        """List files directly inside a folder, optionally filtered by modifiedTime."""
        q = f"'{folder_id}' in parents and trashed=false"
        if since:
            q += f" and modifiedTime > '{since}'"
        return self.search(q)

    def find_folder(self, name: str, parent_id: str) -> Optional[str]:
        """Return folder ID if a subfolder with this name exists, else None."""
        results = self.search(
            f"name='{name}' and '{parent_id}' in parents "
            f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        return results[0]["id"] if results else None

    # ── File metadata ─────────────────────────────────────────────────────────

    def get_metadata(self, file_id: str) -> dict:
        return self._get(f"/files/{file_id}", params={"fields": FILE_FIELDS})

    def verify_folder(self, folder_id: str) -> bool:
        """Return True if a folder ID resolves and is not trashed."""
        try:
            f = self._get(f"/files/{folder_id}", params={"fields": "id,trashed"})
            return not f.get("trashed", True)
        except requests.HTTPError:
            return False

    # ── Write operations ──────────────────────────────────────────────────────

    def move(self, file_id: str, add_parent: str, remove_parent: str,
             new_name: Optional[str] = None) -> dict:
        """Move a file, optionally renaming it in the same call."""
        body = {"name": new_name} if new_name else None
        return self._patch(
            f"/files/{file_id}",
            params={"addParents": add_parent, "removeParents": remove_parent, "fields": "id,name,parents"},
            body=body,
        )

    def trash(self, file_id: str) -> dict:
        """Move a file to Drive Trash (soft delete, 30-day recovery)."""
        return self._patch(f"/files/{file_id}", params={"fields": "id"}, body={"trashed": True})

    def create_folder(self, name: str, parent_id: str) -> str:
        """Create a subfolder and return its ID."""
        result = self._post("/files?fields=id", {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        })
        return result["id"]

    def get_or_create_folder(self, name: str, parent_id: str) -> str:
        """Return existing folder ID or create it."""
        existing = self.find_folder(name, parent_id)
        return existing if existing else self.create_folder(name, parent_id)

    # ── Content ───────────────────────────────────────────────────────────────

    def read_content(self, file_id: str, mime: str = None) -> bytes:
        """Download file content. For Google Docs/Sheets, export as plain text."""
        if mime:
            resp = requests.get(
                f"{DRIVE_BASE}/files/{file_id}/export",
                headers=self.headers,
                params={"mimeType": mime},
                timeout=30,
            )
        else:
            resp = requests.get(
                f"{DRIVE_BASE}/files/{file_id}",
                headers=self.headers,
                params={"alt": "media"},
                timeout=30,
            )
        resp.raise_for_status()
        return resp.content

    def read_pdf_as_base64(self, file_id: str) -> str:
        """Download a PDF and return as base64 string for Claude vision."""
        content = self.read_content(file_id)
        return base64.b64encode(content).decode("utf-8")

    # ── State file helpers ────────────────────────────────────────────────────

    def find_in_root(self, filename: str) -> Optional[str]:
        """Return file ID if filename exists in Drive root, else None."""
        results = self.search(
            f"name='{filename}' and 'root' in parents and trashed=false",
            page_size=5,
        )
        return results[0]["id"] if results else None

    def upload_text(self, filename: str, content: str, existing_id: Optional[str] = None) -> str:
        """Create or replace a plain-text file in Drive root."""
        if existing_id:
            try:
                requests.delete(
                    f"{DRIVE_BASE}/files/{existing_id}",
                    headers=self.headers,
                    timeout=10,
                ).raise_for_status()
            except Exception:
                pass

        metadata = {"name": filename, "parents": ["root"]}
        files = {
            "metadata": ("metadata", str(metadata).replace("'", '"'), "application/json"),
            "file": ("file", content, "text/plain"),
        }
        resp = requests.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id",
            headers={"Authorization": self.headers["Authorization"]},
            files=files,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["id"]
