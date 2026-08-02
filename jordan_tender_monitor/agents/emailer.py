"""
Emailer agent: Microsoft Graph, falling back to SMTP, falling back to disk.

Credentials are read from the environment and are never printed, logged or
included in an exception message. When something fails, the log says which
method failed and why in general terms -- never with the secret in it.

SECURITY NOTE, repeated here because it is easy to skip in the README: if
Mail.Send is granted as an Azure APPLICATION permission it is TENANT-WIDE. The
app registration can then send mail as any mailbox in the organisation, so a
leaked client secret becomes an organisation-wide mail-sending capability.
Scope it to the one mailbox with an ApplicationAccessPolicy:

    New-ApplicationAccessPolicy -AppId <client-id> \\
      -PolicyScopeGroupId tender-monitor@yourdomain.com \\
      -AccessRight RestrictAccess \\
      -Description "Restrict Jordan tender monitor to its own mailbox"
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

from .. import config

log = logging.getLogger(__name__)

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_SEND = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


@dataclass
class DeliveryResult:
    method: str          # "graph" | "smtp" | "file" | "skipped"
    sent: bool
    detail: str = ""


def _attachment_parts(paths: list[Path]) -> list[tuple[str, str, bytes]]:
    parts = []
    for path in paths:
        if not path or not Path(path).exists():
            continue
        data = Path(path).read_bytes()
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        parts.append((Path(path).name, ctype, data))
    return parts


# ---------------------------------------------------------------------------
# Microsoft Graph
# ---------------------------------------------------------------------------


def _graph_token() -> str | None:
    if not (config.AZURE_TENANT_ID and config.AZURE_CLIENT_ID
            and config.AZURE_CLIENT_SECRET):
        return None
    try:
        import msal
    except ImportError:
        log.error("msal is not installed; cannot use Microsoft Graph")
        return None

    app = msal.ConfidentialClientApplication(
        client_id=config.AZURE_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{config.AZURE_TENANT_ID}",
        client_credential=config.AZURE_CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=[GRAPH_SCOPE])
    if not isinstance(result, dict) or "access_token" not in result:
        # Log the error CODE only. The response can echo request details, and
        # this line must never become a place a secret appears.
        log.error("Graph token request failed: %s",
                  (result or {}).get("error", "unknown error"))
        return None
    return result["access_token"]


def send_via_graph(subject: str, html_body: str, recipients: list[str],
                   cc: list[str], attachments: list[Path]) -> DeliveryResult:
    import requests

    token = _graph_token()
    if not token:
        return DeliveryResult("graph", False, "no usable Azure credentials")
    sender = config.SENDER_EMAIL
    if not sender:
        return DeliveryResult("graph", False, "SENDER_EMAIL is not set")

    message = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": html_body},
        "toRecipients": [{"emailAddress": {"address": a}} for a in recipients],
        "ccRecipients": [{"emailAddress": {"address": a}} for a in cc],
        "attachments": [
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": name,
                "contentType": ctype,
                "contentBytes": base64.b64encode(data).decode("ascii"),
            }
            for name, ctype, data in _attachment_parts(attachments)
        ],
    }

    try:
        response = requests.post(
            GRAPH_SEND.format(sender=sender),
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={"message": message, "saveToSentItems": True},
            timeout=config.REQUEST_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        return DeliveryResult("graph", False, f"{type(exc).__name__} contacting Graph")

    if response.status_code in (200, 202):
        return DeliveryResult("graph", True, f"sent to {len(recipients)} recipient(s)")
    return DeliveryResult("graph", False, f"Graph returned HTTP {response.status_code}")


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------


def send_via_smtp(subject: str, html_body: str, text_body: str,
                  recipients: list[str], cc: list[str],
                  attachments: list[Path]) -> DeliveryResult:
    if not (config.SMTP_USER and config.SMTP_PASS):
        return DeliveryResult("smtp", False, "no SMTP credentials")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.SENDER_EMAIL or config.SMTP_USER
    message["To"] = ", ".join(recipients)
    if cc:
        message["Cc"] = ", ".join(cc)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    for name, ctype, data in _attachment_parts(attachments):
        maintype, _, subtype = ctype.partition("/")
        message.add_attachment(data, maintype=maintype,
                               subtype=subtype or "octet-stream", filename=name)

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=60) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(message)
    except smtplib.SMTPAuthenticationError:
        return DeliveryResult(
            "smtp", False,
            "authentication rejected - most Office 365 tenants disable SMTP "
            "basic auth by default; use Microsoft Graph instead")
    except Exception as exc:  # noqa: BLE001
        return DeliveryResult("smtp", False, f"{type(exc).__name__} during SMTP send")

    return DeliveryResult("smtp", True, f"sent to {len(recipients)} recipient(s)")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def deliver(subject: str, html_body: str, text_body: str,
            attachments: list[Path], written: dict[str, Path] | None = None,
            force_file_only: bool = False) -> DeliveryResult:
    """Try each configured method in turn; fall back to the files on disk.

    A credential problem degrades to "the report is in output/" rather than to
    a lost run. The report is written before this is called, so nothing is ever
    riding on delivery succeeding.
    """
    recipients = config.EMAIL_RECIPIENTS
    cc = config.EMAIL_CC

    if force_file_only or config.EMAIL_METHOD == "none":
        return DeliveryResult("file", True, "file-only mode; nothing sent")

    if not recipients:
        return DeliveryResult(
            "file", True,
            "no EMAIL_RECIPIENTS set in .env - the report was written to "
            f"{config.OUTPUT_DIR} and no mail was sent")

    failures = []
    for method in config.EMAIL_FALLBACK_CHAIN:
        if method == "graph":
            result = send_via_graph(subject, html_body, recipients, cc, attachments)
        elif method == "smtp":
            result = send_via_smtp(subject, html_body, text_body, recipients, cc,
                                   attachments)
        else:
            joined = "; ".join(failures) or "no method attempted"
            return DeliveryResult(
                "file", True,
                f"no mail sent ({joined}). The report is in {config.OUTPUT_DIR}")

        if result.sent:
            return result
        failures.append(f"{method}: {result.detail}")
        log.warning("delivery via %s failed: %s", method, result.detail)

    return DeliveryResult("file", True,
                          f"no mail sent ({'; '.join(failures)}). "
                          f"The report is in {config.OUTPUT_DIR}")
