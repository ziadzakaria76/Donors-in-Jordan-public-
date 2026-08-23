"""Credential handling.

Nothing here is hypothetical: SAM.gov takes its key as a query parameter, and
requests' exception messages embed the full URL, so an unreachable host would
otherwise print the key to the console and write it into the error field of
every JSON report -- which is then attached to an email.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from syria_monitor.fetch import Fetcher, TransportError, redact
from syria_monitor.portals import REGISTRY
from syria_monitor.report import write_json

SECRET = "sk-live-DEADBEEF1234567890"


@pytest.mark.parametrize("raw", [
    f"https://api.sam.gov/prod/opportunities/v2/search?api_key={SECRET}&limit=100",
    f"https://example.test/x?token={SECRET}",
    f"https://example.test/x?client_secret={SECRET}&y=1",
    f"ConnectionError: HTTPSConnectionPool ... url: /search?api_key={SECRET}",
])
def test_secrets_are_redacted_from_surfaced_text(raw):
    cleaned = redact(raw)
    assert SECRET not in cleaned
    assert "<redacted>" in cleaned


def test_non_secret_parameters_survive_redaction():
    cleaned = redact("https://example.test/search?limit=100&ncode=SY&postedFrom=01/01/2026")
    assert "limit=100" in cleaned and "ncode=SY" in cleaned


def test_transport_error_from_a_failing_request_carries_no_key(monkeypatch):
    fetcher = Fetcher()

    def explode(*args, **kwargs):
        raise requests.ConnectionError(
            f"HTTPSConnectionPool(host='api.sam.gov', port=443): "
            f"Max retries exceeded with url: /v2/search?api_key={SECRET}")

    monkeypatch.setattr(fetcher.session, "request", explode)
    with pytest.raises(TransportError) as excinfo:
        fetcher.get("https://api.sam.gov/prod/opportunities/v2/search")
    assert SECRET not in str(excinfo.value)


def test_a_failing_portal_does_not_leak_its_key_into_the_report(monkeypatch, profile, gate,
                                                                config, tmp_path):
    monkeypatch.setenv("SAM_API_KEY", SECRET)

    class LeakyFetcher(Fetcher):
        def json(self, url, **kwargs):
            params = kwargs.get("params") or {}
            raise TransportError(redact(
                f"ConnectionError: url {url}?api_key={params.get('api_key', '')}"))

    outcome = REGISTRY["samgov"]({}, profile, LeakyFetcher(), gate).collect()
    assert outcome.available is False
    assert SECRET not in (outcome.error or "")

    class Result:
        started = "2026-08-23T00:00:00+00:00"
        tenders: list = []
        excluded: list = []
        portals = [outcome]
        counts: dict = {}
        screening_status: list = []
        screening_error = None
        duplicates_collapsed = 0
        expired_dropped = 0

        def subject(self):
            return "test"

    path = write_json(Result(), tmp_path / "r.json", profile)
    assert SECRET not in path.read_text(encoding="utf-8")


def test_gitignore_covers_everything_the_run_writes():
    """.cache/ holds downloaded sanctions lists; output/ and *.db hold run state."""
    ignored = set(Path(".gitignore").read_text(encoding="utf-8").split())
    for pattern in (".env", "*.db", "output/", "__pycache__/", "*.pyc", ".cache/"):
        assert pattern in ignored, f"{pattern} is written at runtime but not ignored"


def test_graph_mailer_never_echoes_a_response_body(monkeypatch):
    """A failed token request must not quote the response: it can contain the
    request payload, secret included."""
    from syria_monitor.delivery import GraphMailer, MailError

    for name in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET", "GRAPH_SENDER"):
        monkeypatch.setenv(name, SECRET if "SECRET" in name else "value")

    mailer = GraphMailer()

    class Response:
        status_code = 400
        text = f"{{\"error\":\"invalid_client\",\"client_secret\":\"{SECRET}\"}}"

        def json(self):
            return {"error": "invalid_client"}

    monkeypatch.setattr(mailer.session, "post", lambda *a, **k: Response())
    with pytest.raises(MailError) as excinfo:
        mailer.token()
    assert SECRET not in str(excinfo.value)
    assert "400" in str(excinfo.value)
