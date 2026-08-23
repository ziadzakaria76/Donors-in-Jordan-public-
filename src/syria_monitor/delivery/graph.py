"""Microsoft Graph delivery.

Credentials are read from the environment and never logged: no code path here
prints a token, a secret or a full request body.

If Mail.Send is granted as an APPLICATION permission it is tenant-wide -- the
app can send as any mailbox in the tenant. Scope it to one mailbox with an
ApplicationAccessPolicy; the README carries the PowerShell.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

import requests

TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
SEND_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
SCOPE = "https://graph.microsoft.com/.default"

# Graph rejects a simple sendMail whose total payload is too large. Past that,
# the report goes out without attachments rather than failing to arrive.
MAX_TOTAL_ATTACHMENT_BYTES = 3 * 1024 * 1024


class MailError(RuntimeError):
    pass


def recipients_from_env() -> tuple[list[str], list[str]]:
    def split(name: str) -> list[str]:
        return [v.strip() for v in (os.environ.get(name) or "").split(",") if v.strip()]
    return split("REPORT_TO"), split("REPORT_CC")


class GraphMailer:
    def __init__(self, session: Optional[requests.Session] = None):
        self.tenant = os.environ.get("GRAPH_TENANT_ID")
        self.client_id = os.environ.get("GRAPH_CLIENT_ID")
        self.secret = os.environ.get("GRAPH_CLIENT_SECRET")
        self.sender = os.environ.get("GRAPH_SENDER")
        self.session = session or requests.Session()

    @property
    def configured(self) -> bool:
        return all([self.tenant, self.client_id, self.secret, self.sender])

    def missing(self) -> list[str]:
        names = {"GRAPH_TENANT_ID": self.tenant, "GRAPH_CLIENT_ID": self.client_id,
                 "GRAPH_CLIENT_SECRET": self.secret, "GRAPH_SENDER": self.sender}
        return [name for name, value in names.items() if not value]

    def token(self) -> str:
        if not self.configured:
            raise MailError(f"missing credentials: {', '.join(self.missing())}")
        response = self.session.post(
            TOKEN_URL.format(tenant=self.tenant),
            data={"client_id": self.client_id, "client_secret": self.secret,
                  "grant_type": "client_credentials", "scope": SCOPE},
            timeout=30)
        if response.status_code != 200:
            # Deliberately does not echo the response body: it can contain the
            # request payload, including the secret.
            raise MailError(f"token request failed with HTTP {response.status_code}")
        token = response.json().get("access_token")
        if not token:
            raise MailError("token response contained no access_token")
        return token

    @staticmethod
    def build_message(subject: str, html: str, to: list[str], cc: list[str],
                      attachments: list[Path]) -> tuple[dict, list[str]]:
        notes: list[str] = []
        payloads, total = [], 0
        for path in attachments:
            path = Path(path)
            if not path.exists():
                continue
            data = path.read_bytes()
            total += len(data)
            payloads.append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": path.name,
                "contentBytes": base64.b64encode(data).decode("ascii"),
            })
        if total > MAX_TOTAL_ATTACHMENT_BYTES:
            payloads = []
            notes.append(f"attachments omitted: {total/1048576:.1f} MB exceeds the "
                         f"{MAX_TOTAL_ATTACHMENT_BYTES/1048576:.0f} MB sendMail limit -- "
                         "files are in the output directory / CI artifacts")
            html += ("<p style=\"color:#b02a2a\"><b>Attachments omitted this run: the report "
                     "exceeded the mail size limit. The files are in the run's output "
                     "directory.</b></p>")

        message = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html},
                "toRecipients": [{"emailAddress": {"address": a}} for a in to],
                "ccRecipients": [{"emailAddress": {"address": a}} for a in cc],
                "attachments": payloads,
            },
            "saveToSentItems": True,
        }
        return message, notes

    def send(self, subject: str, html: str, to: list[str], cc: Optional[list[str]] = None,
             attachments: Optional[list[Path]] = None) -> list[str]:
        if not to:
            raise MailError("no recipients: set REPORT_TO in .env")
        message, notes = self.build_message(subject, html, to, cc or [], attachments or [])
        response = self.session.post(
            SEND_URL.format(sender=self.sender),
            headers={"Authorization": f"Bearer {self.token()}",
                     "Content-Type": "application/json"},
            json=message, timeout=60)
        if response.status_code not in (200, 202):
            raise MailError(f"sendMail failed with HTTP {response.status_code}")
        return notes
