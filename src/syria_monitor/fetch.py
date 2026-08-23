"""Polite HTTP. One session, one throttle, one retry policy for every portal."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/126.0.0.0 Safari/537.36")

# Do not lower this to speed things up. These are public-interest portals run on
# modest infrastructure and a monitor has no business hammering them.
HOST_DELAY_SECONDS = 2.0

_last_request: dict[str, float] = {}
_lock = threading.Lock()


# Some portals take credentials as query parameters (SAM.gov's api_key is one),
# and requests' exception messages embed the full URL. Without this, a single
# unreachable host prints the key to the console and writes it into the error
# field of every JSON report -- which is then attached to an email.
# The (?<![\w-]) guard matters: without it "code" matches inside SAM.gov's own
# ncode= parameter and the redaction eats the country filter.
_SECRET_PARAM_RE = re.compile(
    r"(?<![\w-])((?:api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token"
    r"|token|secret|signature|password|passwd|pwd|auth|code)=)[^&\s\"']+",
    re.IGNORECASE)


def redact(text: str) -> str:
    """Strip credential-bearing query parameters from anything we surface."""
    return _SECRET_PARAM_RE.sub(r"\1<redacted>", str(text))


class TransportError(RuntimeError):
    """Network-level failure: wrong URL, blocked host, DNS, TLS, timeout."""


@dataclass
class Response:
    url: str
    status: int
    text: str
    headers: dict

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def _throttle(url: str) -> None:
    host = urlparse(url).netloc
    with _lock:
        last = _last_request.get(host)
        now = time.monotonic()
        if last is not None:
            wait = HOST_DELAY_SECONDS - (now - last)
            if wait > 0:
                time.sleep(wait)
        _last_request[host] = time.monotonic()


class Fetcher:
    def __init__(self, timeout: int = 30, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "en,ar;q=0.8,de;q=0.6,fr;q=0.6",
        })

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=2, min=2, max=16),
           retry=retry_if_exception_type(requests.RequestException),
           reraise=True)
    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        _throttle(url)
        return self.session.request(method, url, timeout=self.timeout, **kwargs)

    def get(self, url: str, **kwargs) -> Response:
        try:
            r = self._request("GET", url, **kwargs)
        except requests.RequestException as exc:
            raise TransportError(redact(f"{type(exc).__name__}: {exc}")) from exc
        return Response(url=r.url, status=r.status_code, text=r.text, headers=dict(r.headers))

    def post(self, url: str, **kwargs) -> Response:
        try:
            r = self._request("POST", url, **kwargs)
        except requests.RequestException as exc:
            raise TransportError(redact(f"{type(exc).__name__}: {exc}")) from exc
        return Response(url=r.url, status=r.status_code, text=r.text, headers=dict(r.headers))

    def json(self, url: str, **kwargs):
        try:
            r = self._request("GET", url, **kwargs)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            raise TransportError(redact(f"{type(exc).__name__}: {exc}")) from exc
        except ValueError as exc:
            raise TransportError(redact(f"response was not JSON: {exc}")) from exc
