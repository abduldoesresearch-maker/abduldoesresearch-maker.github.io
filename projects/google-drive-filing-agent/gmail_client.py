"""Gmail REST API v1 — send email via OAuth access token."""

import base64
import email.mime.text
import requests


GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"


class GmailClient:
    def __init__(self, access_token: str):
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def send(self, to: str, subject: str, body: str) -> dict:
        """Send a plain-text email and return the sent message metadata."""
        msg = email.mime.text.MIMEText(body, "plain")
        msg["From"] = to
        msg["To"] = to
        msg["Subject"] = subject

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

        resp = requests.post(
            f"{GMAIL_BASE}/users/me/messages/send",
            headers=self.headers,
            json={"raw": raw},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
