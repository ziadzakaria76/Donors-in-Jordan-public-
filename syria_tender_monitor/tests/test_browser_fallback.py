"""The JavaScript fallback.

Most of this runs without Playwright: the escalation logic is tested with a
stub renderer so CI needs no browser. The last test is the real thing -- it
serves a client-rendered page over localhost and drives Chromium at it -- and
skips itself when Playwright or a usable Chromium is absent.
"""

from __future__ import annotations

import http.server
import os
import socket
import threading
from functools import partial

import pytest

from syria_monitor import browser as browser_mod
from syria_monitor.extraction import diagnose
from syria_monitor.fetch import Fetcher
from syria_monitor.portals.base import HtmlPortal

from conftest import fixture

JS_SHELL = """<html><head><title>Notices</title></head><body>
<div id="app-root"></div>
<script>
  const rows = [
    ["Rehabilitation of water pumping stations, Aleppo", "30-Sep-2026", "/n/1"],
    ["Technical assistance, public financial management, Damascus, Syria", "12-Oct-2026", "/n/2"],
    ["Supervision of health facility works, Homs", "04-Oct-2026", "/n/3"],
    ["Road maintenance consultancy, Casablanca", "20-Oct-2026", "/n/4"]
  ];
  const list = document.createElement("div");
  rows.forEach(function (r) {
    const item = document.createElement("div");
    item.innerHTML = '<a href="' + r[2] + '">' + r[0] + '</a><span>Deadline: ' + r[1] + '</span>';
    list.appendChild(item);
  });
  document.getElementById("app-root").appendChild(list);
</script></body></html>"""


class ShellPortal(HtmlPortal):
    """Serves a JS shell over plain HTTP; a renderer must supply the content."""

    name = "shell"
    label = "Shell"
    url = "https://shell.example/notices"

    def fetch_page(self, label, url):
        return JS_SHELL, 200


def build(cls, profile, gate, cfg=None):
    return cls(cfg or {}, profile, Fetcher(), gate)


# --------------------------------------------------------------- the decision
@pytest.mark.parametrize("diagnosis,expected", [
    ("js_shell: page renders client-side -- playwright install chromium", True),
    ("bot_wall: use a different network or drive it with Playwright", True),
    ("layout_change: page fetched fine but no layer found a listing", False),
    ("transport: HTTP 404 -- wrong URL or blocked host", False),
    (None, False),
])
def test_only_the_diagnoses_a_browser_can_fix_trigger_one(diagnosis, expected):
    """Rendering a layout change or a dead URL wastes time and hides the cause."""
    assert HtmlPortal.needs_browser(diagnosis) is expected


def test_the_shell_page_is_diagnosed_as_needing_a_browser():
    assert diagnose(JS_SHELL, 200).startswith("js_shell")


# ------------------------------------------------------ escalation, stubbed
@pytest.fixture
def stub_renderer(monkeypatch):
    calls = []

    def fake_render(url, **kwargs):
        calls.append((url, kwargs))
        return fixture("nav_trap.html"), 200

    monkeypatch.setattr(browser_mod, "render", fake_render)
    return calls


def test_a_js_shell_escalates_to_the_browser_and_recovers_rows(profile, gate, stub_renderer):
    outcome = build(ShellPortal, profile, gate).collect()
    assert stub_renderer, "the browser was never tried"
    assert outcome.rendered_with_browser is True
    assert outcome.tenders
    assert "rendered in a browser" in outcome.status_line


def test_plain_http_is_always_tried_first(profile, gate, monkeypatch, stub_renderer):
    """A static page must never launch Chromium."""
    class StaticPortal(ShellPortal):
        def fetch_page(self, label, url):
            return fixture("nav_trap.html"), 200

    outcome = build(StaticPortal, profile, gate).collect()
    assert outcome.tenders
    assert outcome.rendered_with_browser is False
    assert stub_renderer == [], "a static page should not have launched a browser"


def test_browser_never_mode_skips_it(profile, gate, stub_renderer):
    outcome = build(ShellPortal, profile, gate, {"browser": "never"}).collect()
    assert stub_renderer == []
    assert outcome.available is False          # reported, not silently empty
    assert "js_shell" in outcome.error


def test_browser_always_mode_renders_without_trying_http_first(profile, gate, stub_renderer):
    outcome = build(ShellPortal, profile, gate, {"browser": "always"}).collect()
    assert len(stub_renderer) == 1
    assert outcome.tenders


def test_portal_config_passes_timeouts_through(profile, gate, stub_renderer):
    build(ShellPortal, profile, gate,
          {"browser_timeout_ms": 12345, "browser_settle_ms": 999,
           "browser_wait_for": ".row"}).collect()
    _, kwargs = stub_renderer[0]
    assert kwargs["timeout_ms"] == 12345
    assert kwargs["settle_ms"] == 999
    assert kwargs["wait_for"] == ".row"


# ------------------------------------------------------ missing Playwright
def test_a_missing_browser_is_reported_not_raised(profile, gate, monkeypatch):
    def unavailable(url, **kwargs):
        raise browser_mod.BrowserUnavailable(browser_mod.INSTALL_HINT)

    monkeypatch.setattr(browser_mod, "render", unavailable)
    outcome = build(ShellPortal, profile, gate).collect()

    assert outcome.available is False          # this portal could not be read
    assert outcome.rendered_with_browser is False
    assert "pip install playwright" in (outcome.browser_note or "")
    assert "js_shell" in outcome.error


def test_install_hint_names_both_commands():
    assert "pip install playwright" in browser_mod.INSTALL_HINT
    assert "playwright install chromium" in browser_mod.INSTALL_HINT


# ------------------------------------------------------------ the real thing
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = JS_SHELL.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _chromium_present() -> bool:
    """Is there a Chromium this machine can actually launch?

    By launching one, because nothing cheaper answers it honestly:

    - `_executable_path()` answers "is there an override". It returns None to
      mean "no override, let Playwright use its own download" -- the normal,
      working case on a runner that just ran `playwright install chromium`.
      Reading that None as "no browser" failed this test on exactly the
      machines the browser job exists to cover, while passing on a sandbox that
      happens to set PLAYWRIGHT_BROWSERS_PATH.
    - `chromium.executable_path` names the full browser, but a headless
      `launch()` runs the separate headless-shell build. Either can be present
      without the other.

    So do what `browser.render()` does, with the same arguments, and see. It
    costs about a second when a browser is there and fails fast when it is not.
    """
    if not browser_mod.available():
        return False
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False

    launch_kwargs = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
    explicit = browser_mod._executable_path()
    if explicit:
        launch_kwargs["executable_path"] = explicit
    try:
        with sync_playwright() as playwright:
            playwright.chromium.launch(**launch_kwargs).close()
        return True
    except Exception:
        return False


chromium_missing = not _chromium_present()

# CI sets REQUIRE_BROWSER=1 in the job that installs Playwright. Without it a
# broken install would show up as a skip, and the only end-to-end-verified path
# in this repository would quietly stop being verified.
REQUIRE_BROWSER = os.environ.get("REQUIRE_BROWSER") == "1"


@pytest.mark.skipif(chromium_missing and not REQUIRE_BROWSER,
                    reason="Playwright or Chromium not installed")
def test_chromium_actually_renders_a_client_side_listing(profile, gate):
    """End to end against a real browser, over localhost -- no external network.

    Plain HTTP returns a page with no rows; Chromium runs the script and the
    same extraction cascade then finds the listing.
    """
    assert not chromium_missing, (
        "REQUIRE_BROWSER=1 but Playwright or Chromium is unavailable -- the "
        "install step did not do what it claimed")
    port = _free_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), partial(_Handler))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{port}/notices"

        class LivePortal(HtmlPortal):
            name = "live_shell"
            label = "Live shell"

        LivePortal.url = url
        portal = build(LivePortal, profile, gate)
        outcome = portal.collect()

        assert outcome.rendered_with_browser is True, outcome.error
        titles = [t.title for t in outcome.tenders]
        assert any("Aleppo" in t for t in titles), titles
        assert not any("Casablanca" in t for t in titles), "the country gate still applies"
    finally:
        server.shutdown()
        server.server_close()
