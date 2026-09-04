"""HTTP access, with the politeness floor enforced in code.

The delay is a floor rather than a setting: `Fetcher` raises if constructed
below MIN_DELAY_SECONDS, so no config edit and no --flag can make the scanner
hammer a hospital's careers portal.

Network failures are returned as structured detail rather than raised as bare
tracebacks, because the run has to continue to the next source and the reason
has to survive into Run status.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from .config import MIN_DELAY_SECONDS

USER_AGENT = (
    "job-scanner/1.0 (+personal job search; contact via repository owner) "
    "python-requests"
)


@dataclass
class Response:
    ok: bool
    status_code: int = 0
    text: str = ""
    json_body: object = None
    error: str = ""
    url: str = ""

    @property
    def blocked_by_policy(self) -> bool:
        """A refusal by the egress gateway rather than by the site itself."""
        markers = (
            "connect_rejected",
            "proxy refused",
            "tunnel connection failed",
            "403 to connect",
        )
        haystack = self.error.lower()
        return any(marker in haystack for marker in markers)


class Fetcher:
    def __init__(self, delay: float = MIN_DELAY_SECONDS, timeout: int = 30):
        if delay < MIN_DELAY_SECONDS:
            raise ValueError(
                f"delay {delay}s is below the {MIN_DELAY_SECONDS}s floor; the floor "
                "is not configurable"
            )
        self.delay = delay
        self.timeout = timeout
        self._last_request_at = 0.0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if self._last_request_at and elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_at = time.monotonic()

    def get(self, url, **kwargs):
        return self._request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._request("POST", url, **kwargs)

    def _request(self, method: str, url: str, **kwargs) -> Response:
        self._wait()
        try:
            raw = self._session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.exceptions.ProxyError as exc:
            return Response(ok=False, error=f"proxy refused: {exc}", url=url)
        except requests.exceptions.SSLError as exc:
            return Response(ok=False, error=f"TLS failure: {exc}", url=url)
        except requests.exceptions.ConnectionError as exc:
            return Response(ok=False, error=f"connection failed: {exc}", url=url)
        except requests.exceptions.Timeout:
            return Response(ok=False, error=f"timed out after {self.timeout}s", url=url)
        except requests.exceptions.RequestException as exc:
            return Response(ok=False, error=f"request failed: {exc}", url=url)

        body = None
        content_type = raw.headers.get("content-type", "")
        if "json" in content_type.lower():
            try:
                body = raw.json()
            except ValueError as exc:
                return Response(
                    ok=False,
                    status_code=raw.status_code,
                    text=raw.text[:2000],
                    error=f"content-type claimed JSON but body did not parse: {exc}",
                    url=url,
                )

        if raw.status_code >= 400:
            return Response(
                ok=False,
                status_code=raw.status_code,
                text=raw.text[:2000],
                json_body=body,
                error=f"HTTP {raw.status_code}",
                url=url,
            )
        return Response(
            ok=True, status_code=raw.status_code, text=raw.text, json_body=body, url=url
        )
