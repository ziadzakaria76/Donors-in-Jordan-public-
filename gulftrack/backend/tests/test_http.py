"""Polite fetching.

These rules are not decoration. A scraper that ignores robots.txt or hammers a
contractor's careers page gets blocked, and a blocked source is one Fadi stops
hearing from.
"""

from __future__ import annotations

import time

import httpx
import pytest

from app.adapters.http import FetchBlocked, FetchFailed, PoliteClient, USER_AGENT


def make_client(handler, **kw):
    transport = httpx.MockTransport(handler)
    inner = httpx.Client(
        transport=transport,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    kw.setdefault("delay_seconds", 0.0)
    return PoliteClient(client=inner, **kw)


def responder(routes, calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        for suffix, response in routes.items():
            if request.url.path.endswith(suffix):
                return response() if callable(response) else response
        return httpx.Response(404, text="not found")
    return handler


# -- robots.txt --------------------------------------------------------------

def test_a_disallowed_path_is_refused_without_being_requested():
    calls = []
    client = make_client(responder({
        "/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /careers"),
        "/careers": httpx.Response(200, text="jobs"),
    }, calls))

    with pytest.raises(FetchBlocked):
        client.get("https://example.com/careers")

    assert [r.url.path for r in calls] == ["/robots.txt"], "the page must not be fetched"


def test_an_allowed_path_proceeds():
    client = make_client(responder({
        "/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /admin"),
        "/careers": httpx.Response(200, text="jobs"),
    }))
    assert client.get("https://example.com/careers").text == "jobs"


def test_absent_robots_is_treated_as_permission():
    client = make_client(responder({
        "/robots.txt": httpx.Response(404),
        "/careers": httpx.Response(200, text="jobs"),
    }))
    assert client.get("https://example.com/careers").status_code == 200


def test_unreadable_robots_is_treated_as_refusal():
    """If we cannot read the rules, assume we are not welcome."""
    def handler(request):
        if request.url.path.endswith("robots.txt"):
            raise httpx.ConnectError("connection reset")
        return httpx.Response(200, text="jobs")

    client = make_client(handler)
    with pytest.raises(FetchBlocked):
        client.get("https://example.com/careers")


def test_robots_is_fetched_once_per_domain():
    calls = []
    client = make_client(responder({
        "/robots.txt": httpx.Response(200, text="User-agent: *\nAllow: /"),
        "/a": httpx.Response(200, text="a"),
        "/b": httpx.Response(200, text="b"),
    }, calls))

    client.get("https://example.com/a")
    client.get("https://example.com/b")

    assert [r.url.path for r in calls].count("/robots.txt") == 1


# -- pacing ------------------------------------------------------------------

def test_requests_to_one_domain_are_spaced_out():
    client = make_client(responder({
        "/robots.txt": httpx.Response(200, text=""),
        "/a": httpx.Response(200, text="a"),
    }), delay_seconds=0.25)

    client.get("https://example.com/a")
    started = time.monotonic()
    client.get("https://example.com/a")
    elapsed = time.monotonic() - started

    assert elapsed >= 0.2, "a second request must wait its turn"


def test_the_user_agent_identifies_us_and_offers_contact():
    calls = []
    client = make_client(responder({
        "/robots.txt": httpx.Response(200, text=""),
        "/a": httpx.Response(200, text="a"),
    }, calls))
    client.get("https://example.com/a")

    agent = calls[-1].headers["user-agent"]
    assert "GulfTrack" in agent
    assert "@" in agent, "an honest agent string includes a contact"


# -- retries and failures ----------------------------------------------------

def test_a_rate_limit_is_retried_then_reported():
    attempts = []

    def handler(request):
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(200, text="")
        attempts.append(request)
        return httpx.Response(429, text="slow down")

    client = make_client(handler)
    with pytest.raises(FetchFailed, match="429"):
        client.get("https://example.com/a")
    assert len(attempts) == 3, "429 is retried, not abandoned on the first try"


def test_a_server_error_recovers_if_the_retry_succeeds():
    state = {"n": 0}

    def handler(request):
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(200, text="")
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, text="recovered")

    client = make_client(handler)
    assert client.get("https://example.com/a").text == "recovered"


def test_a_not_found_is_not_retried():
    attempts = []

    def handler(request):
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(200, text="")
        attempts.append(request)
        return httpx.Response(404, text="gone")

    client = make_client(handler)
    with pytest.raises(FetchFailed, match="404"):
        client.get("https://example.com/a")
    assert len(attempts) == 1, "a 404 will not improve on retry"


def test_html_served_where_json_was_expected_is_a_failure_not_an_empty_result():
    """The failure mode that would silently retire every job from a source."""
    client = make_client(responder({
        "/robots.txt": httpx.Response(200, text=""),
        "/api": httpx.Response(
            200, text="<html>maintenance</html>",
            headers={"content-type": "text/html"},
        ),
    }))
    with pytest.raises(FetchFailed, match="instead of JSON"):
        client.get_json("https://example.com/api")


def test_valid_json_is_returned():
    client = make_client(responder({
        "/robots.txt": httpx.Response(200, text=""),
        "/api": httpx.Response(200, json={"items": [1, 2]}),
    }))
    assert client.get_json("https://example.com/api") == {"items": [1, 2]}
