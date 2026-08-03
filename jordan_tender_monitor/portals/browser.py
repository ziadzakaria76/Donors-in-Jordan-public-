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


def render(url: str, wait_for: str | None = None,
           settle_ms: int = 2500) -> str:
    """Load a page in a headless browser and return the rendered HTML.

    wait_for is a CSS selector to wait for before reading the DOM. It is a
    hint, not a requirement: if it never appears the page is still read after
    the settle delay, because a changed class name should degrade to a weak
    result the cascade can diagnose, not to a hard failure.
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
