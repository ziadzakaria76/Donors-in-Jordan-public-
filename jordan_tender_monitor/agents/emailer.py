"""
Agent 4 -- email dispatcher.

Delivery chain: Microsoft Graph -> Office 365 SMTP -> save-to-disk.
Whichever credentials are present win at runtime; nothing is ever logged that
could expose a secret (only which method was attempted and whether it worked).
"""

from __future__ import annotations

import base64
import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import requests

import config

log = logging.getLogger(__name__)

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_SENDMAIL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
MAX_GRAPH_ATTACHMENT_BYTES = 3 * 1024 * 1024  # Graph inline attachment ceiling


def graph_configured() -> bool:
    return all(
        [config.AZURE_TENANT_ID, config.AZURE_CLIENT_ID,
         config.AZURE_CLIENT_SECRET, config.SENDER_EMAIL]
    )


def smtp_configured() -> bool:
    return bool(config.SMTP_USER and config.SMTP_PASS)


MIME_BY_SUFFIX = {
    ".xlsx": ("application",
              "vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ".docx": ("application",
              "vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ".csv": ("text", "csv"),
    ".json": ("application", "json"),
    ".html": ("text", "html"),
}


def _normalise(attachments) -> list[Path]:
    """Accept a single path or a list; drop anything missing."""
    if attachments is None:
        return []
    if isinstance(attachments, (str, Path)):
        attachments = [attachments]
    return [Path(a) for a in attachments if a and Path(a).exists()]


def _mime_for(path: Path) -> tuple[str, str]:
    return MIME_BY_SUFFIX.get(path.suffix.lower(), ("application", "octet-stream"))


# --------------------------------------------------------------------------
# Microsoft Graph
# --------------------------------------------------------------------------
def _graph_token() -> str:
    import msal

    app = msal.ConfidentialClientApplication(
        client_id=config.AZURE_CLIENT_ID,
        client_credential=config.AZURE_CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{config.AZURE_TENANT_ID}",
    )
    result = app.acquire_token_for_client(scopes=[GRAPH_SCOPE])
    if not isinstance(result, dict) or "access_token" not in result:
        # Surface the error code only -- never the token response contents.
        code = (result or {}).get("error", "unknown_error")
        raise RuntimeError(f"Graph token request failed ({code})")
    return result["access_token"]


def send_via_graph(subject: str, body_html: str, attachments=None) -> None:
    token = _graph_token()
    message: dict = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": body_html},
        "toRecipients": [
            {"emailAddress": {"address": address}} for address in config.EMAIL_RECIPIENTS
        ],
    }
    if config.EMAIL_CC:
        message["ccRecipients"] = [
            {"emailAddress": {"address": address}} for address in config.EMAIL_CC
        ]

    parts = []
    for path in _normalise(attachments):
        blob = path.read_bytes()
        if len(blob) > MAX_GRAPH_ATTACHMENT_BYTES:
            log.warning(
                "Attachment %s is %.1f MB, above the inline Graph limit - omitting it",
                path.name, len(blob) / 1e6,
            )
            continue
        maintype, subtype = _mime_for(path)
        parts.append({
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": path.name,
            "contentType": f"{maintype}/{subtype}",
            "contentBytes": base64.b64encode(blob).decode("ascii"),
        })
    if parts:
        message["attachments"] = parts

    response = requests.post(
        GRAPH_SENDMAIL.format(sender=config.SENDER_EMAIL),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"message": message, "saveToSentItems": True},
        timeout=config.REQUEST_TIMEOUT,
    )
    if response.status_code not in (200, 202):
        raise RuntimeError(
            f"Graph sendMail returned HTTP {response.status_code}: {response.text[:300]}"
        )


# --------------------------------------------------------------------------
# Office 365 SMTP
# --------------------------------------------------------------------------
def send_via_smtp(subject: str, body_html: str, attachments=None) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.SMTP_USER
    message["To"] = ", ".join(config.EMAIL_RECIPIENTS)
    if config.EMAIL_CC:
        message["Cc"] = ", ".join(config.EMAIL_CC)
    message.set_content(
        "This report is formatted as HTML. Please view it in an HTML-capable client."
    )
    message.add_alternative(body_html, subtype="html")

    for path in _normalise(attachments):
        maintype, subtype = _mime_for(path)
        message.add_attachment(
            path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name
        )

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=config.REQUEST_TIMEOUT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config.SMTP_USER, config.SMTP_PASS)
        server.send_message(message)


# --------------------------------------------------------------------------
# Dispatcher
# --------------------------------------------------------------------------
def dispatch(
    subject: str,
    body_html: str,
    attachments=None,
    saved_files: dict | None = None,
) -> dict:
    """Try Graph, then SMTP, then fall back to files. Returns a status dict."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    attempts: list[str] = []

    # Recipients come from .env, so a fresh clone has none. Sending with an
    # empty recipient list fails deep inside Graph with an opaque error, so
    # stop here and save the report instead.
    if not config.EMAIL_RECIPIENTS:
        log.warning(
            "No EMAIL_RECIPIENTS set in .env - saving the report instead of sending"
        )
        paths = [str(p) for p in (saved_files or {}).values()]
        return {
            "sent": False, "method": "file", "timestamp": timestamp,
            "recipients": [], "files": paths,
            "attempts": ["no EMAIL_RECIPIENTS configured in .env"],
        }

    order = []
    if config.EMAIL_METHOD == "graph":
        order = [("graph", graph_configured, send_via_graph),
                 ("smtp", smtp_configured, send_via_smtp)]
    elif config.EMAIL_METHOD == "smtp":
        order = [("smtp", smtp_configured, send_via_smtp),
                 ("graph", graph_configured, send_via_graph)]

    for name, is_configured, sender in order:
        if not is_configured():
            attempts.append(f"{name}: not configured")
            log.info("Email method '%s' skipped - credentials not set", name)
            continue
        try:
            sender(subject, body_html, attachments)
            log.info("Report emailed via %s at %s to %s",
                     name, timestamp, ", ".join(config.EMAIL_RECIPIENTS))
            return {
                "sent": True, "method": name, "timestamp": timestamp,
                "recipients": config.EMAIL_RECIPIENTS, "attempts": attempts,
            }
        except Exception as exc:  # noqa: BLE001 - fall through to the next method
            message = str(exc)[:300]
            attempts.append(f"{name}: {message}")
            log.error("Email via %s failed: %s", name, message)

    paths = [str(p) for p in (saved_files or {}).values()]
    log.warning("No email sent. Report saved to: %s", ", ".join(paths) or "output/")
    return {
        "sent": False, "method": "file", "timestamp": timestamp,
        "recipients": config.EMAIL_RECIPIENTS, "attempts": attempts, "files": paths,
    }
