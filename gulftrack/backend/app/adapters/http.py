"""Polite HTTP fetching.

Section 6 sets the rules for anything we are permitted to fetch: respect
robots.txt, no more than one request every 3–5 seconds per domain, an honest
and identifiable User-Agent, and aggressive caching. This module is the only
place in the codebase allowed to make an outbound request, so those rules hold
whether an adapter author remembers them or not.

A courtesy that is also self-interest: a scraper that hammers a Saudi
contractor's careers page gets blocked, and a blocked source is a source Fadi
stops hearing from.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger("gulftrack.http")

USER_AGENT = (
    "GulfTrack/0.1 (personal job-search assistant for a single candidate; "
    "respects robots.txt; contact: ziadzakaria76@gmail.com)"
)

DEFAULT_DELAY_SECONDS = 4.0
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_ATTEMPTS = 3


class FetchBlocked(RuntimeError):
    """robots.txt disallows this path. Not an error to retry — a decision."""


class FetchFailed(RuntimeError):
    """The request did not succeed after retries."""


@dataclass
class _DomainState:
    last_request_at: float = 0.0
    robots: urllib.robotparser.RobotFileParser | None = None
    robots_checked: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


class PoliteClient:
    """One request at a time per domain, spaced out, and only where allowed."""

    def __init__(
        self,
        *,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = USER_AGENT,
        respect_robots: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self._domains: dict[str, _DomainState] = {}
        self._registry_lock = threading.Lock()
        self._client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept-Language": "en,ar;q=0.8",
            },
        )

    # -- politeness ---------------------------------------------------------

    def _state(self, domain: str) -> _DomainState:
        with self._registry_lock:
            if domain not in self._domains:
                self._domains[domain] = _DomainState()
            return self._domains[domain]

    def _wait_turn(self, state: _DomainState) -> None:
        elapsed = time.monotonic() - state.last_request_at
        if state.last_request_at and elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        state.last_request_at = time.monotonic()

    def _robots_allows(self, state: _DomainState, url: str) -> bool:
        if not self.respect_robots:
            return True
        if not state.robots_checked:
            state.robots_checked = True
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            parser = urllib.robotparser.RobotFileParser()
            try:
                response = self._client.get(robots_url)
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                    state.robots = parser
                else:
                    # No robots.txt is permission by convention, not by
                    # accident: an absent file means no restrictions stated.
                    state.robots = None
            except httpx.HTTPError as exc:
                # Could not read the rules. Assume we are not welcome rather
                # than assume we are.
                log.warning("robots.txt unreadable at %s: %s", robots_url, exc)
                state.robots = parser
                parser.parse(["User-agent: *", "Disallow: /"])
        if state.robots is None:
            return True
        return state.robots.can_fetch(self.user_agent, url)

    # -- requests -----------------------------------------------------------

    def get(
        self, url: str, *, params: dict | None = None, headers: dict | None = None
    ) -> httpx.Response:
        return self._request("GET", url, params=params, headers=headers)

    def post(
        self, url: str, *, json_body: Any = None, headers: dict | None = None
    ) -> httpx.Response:
        """POST, under the same politeness rules as GET.

        Several job boards serve their search results only over POST — the
        Workable board API returns "Not Found" to a GET. That is a read, not a
        submission, and nothing in this client is capable of submitting an
        application.
        """
        return self._request("POST", url, json_body=json_body, headers=headers)

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json_body: Any = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        domain = urlparse(url).netloc
        state = self._state(domain)

        with state.lock:
            if not self._robots_allows(state, url):
                raise FetchBlocked(f"robots.txt disallows {url}")

            last_error: Exception | None = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                self._wait_turn(state)
                try:
                    response = self._client.request(
                        method, url, params=params, json=json_body, headers=headers,
                    )
                except httpx.HTTPError as exc:
                    last_error = exc
                    log.warning("%s attempt %s failed: %s", url, attempt, exc)
                else:
                    if response.status_code == 429 or response.status_code >= 500:
                        # Their problem or our pace. Back off rather than
                        # hammer — this is exactly how a source gets banned.
                        last_error = FetchFailed(
                            f"HTTP {response.status_code} from {url}"
                        )
                        log.warning(
                            "%s returned %s, backing off", url, response.status_code
                        )
                    elif response.status_code >= 400:
                        # A 404 or 403 will not improve on retry.
                        raise FetchFailed(f"HTTP {response.status_code} from {url}")
                    else:
                        return response

                if attempt < MAX_ATTEMPTS:
                    time.sleep(self.delay_seconds * (2 ** (attempt - 1)))

            raise FetchFailed(f"{url} failed after {MAX_ATTEMPTS} attempts: {last_error}")

    def get_json(self, url: str, *, params: dict | None = None) -> Any:
        return self._as_json(
            self.get(url, params=params, headers={"Accept": "application/json"}), url
        )

    def post_json(self, url: str, *, json_body: Any = None) -> Any:
        return self._as_json(
            self.post(url, json_body=json_body, headers={"Accept": "application/json"}),
            url,
        )

    @staticmethod
    def _as_json(response: httpx.Response, url: str) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            # An HTML error page served with a 200 is a common portal failure.
            # Treat it as a broken source, never as an empty result set — an
            # empty result would silently retire every job from this source.
            raise FetchFailed(
                f"{url} returned {response.headers.get('content-type')} "
                f"instead of JSON"
            ) from exc

    def close(self) -> None:
        self._client.close()
