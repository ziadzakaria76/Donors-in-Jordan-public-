"""
Headless-browser rendering, for portals whose listing is built by JavaScript.

Used by exactly one portal. UNGM's page arrives as 141 KB of navigation with
not a single notice in it -- the listing is assembled client-side after load,
so no amount of HTTP-level cleverness can read it. Its own search endpoint
returns 395 bytes to a plain POST.

Playwright is therefore an OPTIONAL dependency, kept out of requirements.txt so
a Windows deployment does not pull ~400 MB it may not want. When it is absent,
the portal that needs it fails with an instruction rather than a traceback, and
every other portal is unaffected.

    pip install -r requirements-browser.txt
    playwright install chromium
"""

from __future__ import annotations

import logging

from .. import config
from .base import PortalError

log = logging.getLogger(__name__)

INSTALL_HINT = (
    "this portal renders its listing in JavaScript and needs a headless "
    "browser. Install it with:\n"
    "      pip install -r requirements-browser.txt\n"
    "      playwright install chromium"
)


def available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("playwright") is not None
    except (ImportError, ValueError):
        return False


def _scroll_until_settled(page, row_selector: str, max_scrolls: int,
                          wait_ms: int, url: str) -> int:
    """Scroll to the bottom until the row count stops growing.

    Returns the final row count. Stops on the first pass that adds nothing, so
    a page that does not lazily load costs one wait rather than max_scrolls.

    THE CAP IS LOGGED WHEN IT IS HIT. A silent cap turns "we read everything"
    and "we read the first N and stopped" into the same output, and this
    project has already been bitten by a count that could not distinguish an
    empty portal from a filtered one.
    """
    seen = page.locator(row_selector).count()
    for attempt in range(max_scrolls):
        # Scroll the LAST ROW into view rather than turning the mouse wheel.
        #
        # mouse.wheel scrolls whatever sits under the cursor, which starts at
        # the top-left corner -- the site header, not the listing. On UNGM that
        # loaded a few extra batches and then stalled at 44 rows out of
        # thousands, which reads exactly like "the list has ended" and is not.
        # Asking the last row to scroll itself into view works whatever element
        # is the scroll container.
        try:
            page.locator(row_selector).last.scroll_into_view_if_needed(timeout=5_000)
        except Exception:  # noqa: BLE001 - fall back rather than lose the run
            page.mouse.wheel(0, 40_000)
        page.wait_for_timeout(wait_ms)
        now = page.locator(row_selector).count()
        if now <= seen:
            log.info("browser: %s settled at %d rows after %d scroll(s)",
                     url, now, attempt + 1)
            return now
        seen = now
    log.warning("browser: %s still growing at %d rows when the %d-scroll cap "
                "was reached -- the listing is longer than this run read",
                url, seen, max_scrolls)
    return seen


def _watch_network(page, sink: list) -> None:
    """Record the XHR/fetch calls the page makes, for --capture.

    A rendered listing is a workaround, not an answer: the page is fetching its
    rows from somewhere, and calling that endpoint directly would replace 40
    scrolls with one paged request. Guessing the endpoint has already failed
    once here -- POST /Public/Notice/Search returned 395 bytes -- so watch what
    the UI itself asks for instead.

    Headers are deliberately NOT recorded. They carry cookies and antiforgery
    tokens, and a diagnostic that prints those into a CI log is a credential
    leak wearing a debugging hat. Method, URL, body and response size are
    enough to reconstruct a request by hand.
    """
    def on_response(response):
        request = response.request
        if request.resource_type not in ("xhr", "fetch"):
            return
        try:
            length = len(response.body())
        except Exception:  # noqa: BLE001 - a body may be gone by now
            length = -1
        sink.append({
            "method": request.method,
            "url": request.url,
            "post_data": (request.post_data or "")[:400],
            "status": response.status,
            "bytes": length,
        })

    page.on("response", on_response)


def render(url: str, wait_for: str | None = None,
           settle_ms: int = 2500,
           scroll_for: str | None = None,
           max_scrolls: int = 0,
           scroll_wait_ms: int = 1500,
           network_log: list | None = None) -> str:
    """Load a page in a headless browser and return the rendered HTML.

    wait_for is a CSS selector to wait for before reading the DOM. It is a
    hint, not a requirement: if it never appears the page is still read after
    the settle delay, because a changed class name should degrade to a weak
    result the cascade can diagnose, not to a hard failure.

    scroll_for + max_scrolls handle a listing that lazily loads as you scroll.
    UNGM has thousands of notices, shows fifteen, and carries NO pagination
    control anywhere in its DOM -- the only things --capture found were a
    jQuery datepicker's month arrows and day cells. There is no next page to
    follow; there is more list, once you ask for it.

    Scrolling stops as soon as a pass adds no rows, so a page that is not
    lazily loaded costs one extra wait rather than max_scrolls of them.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PortalError(f"Playwright is not installed - {INSTALL_HINT}", url) from exc

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--disable-dev-shm-usage"])
            try:
                page = browser.new_page(
                    user_agent=config.USER_AGENT,
                    locale="en-GB",
                    viewport={"width": 1440, "height": 2400},
                )
                page.set_default_timeout(config.REQUEST_TIMEOUT * 1000)
                if network_log is not None:
                    _watch_network(page, network_log)
                page.goto(url, wait_until="domcontentloaded")

                if wait_for:
                    try:
                        page.wait_for_selector(wait_for, timeout=15_000)
                    except Exception:  # noqa: BLE001
                        log.info("browser: '%s' never appeared on %s; reading "
                                 "the DOM anyway", wait_for, url)

                # Let client-side rendering finish even when the hint selector
                # was wrong or the page loads its rows in stages.
                page.wait_for_timeout(settle_ms)

                if scroll_for and max_scrolls > 0:
                    _scroll_until_settled(page, scroll_for, max_scrolls,
                                          scroll_wait_ms, url)
                return page.content()
            finally:
                browser.close()
    except PortalError:
        raise
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "Executable doesn" in message or "playwright install" in message:
            raise PortalError(
                "Playwright is installed but its browser is not. "
                "Run: playwright install chromium", url) from exc
        raise PortalError(
            f"headless browser failed - {type(exc).__name__}: {message[:200]}",
            url) from exc
