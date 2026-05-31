"""OAuth token management — reads drive-token.json and refreshes as needed."""

import json
import requests
from pathlib import Path


TOKEN_PATH = Path.home() / ".claude" / "drive-token.json"


def get_access_token() -> str:
    """Return a valid Drive + Gmail access token, refreshing if needed."""
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"Token file not found at {TOKEN_PATH}. "
            "Run the OAuth setup flow first."
        )

    data = json.loads(TOKEN_PATH.read_text())

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": data["client_id"],
            "client_secret": data["client_secret"],
            "refresh_token": data["refresh_token"],
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    resp.raise_for_status()

    token_data = resp.json()
    if "error" in token_data:
        raise RuntimeError(f"Token refresh failed: {token_data['error_description']}")

    return token_data["access_token"]
