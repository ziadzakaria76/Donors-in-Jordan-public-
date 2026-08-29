r"""Playwright fallback for JavaScript-rendered portals.

Optional by design. Plain HTTP is tried first for every page, and a browser is
launched only when extraction found nothing AND the diagnosis says the page is
a client-rendered shell (or a bot wall). Rendering every page would be slower,
heavier, and ruder to the portals for no benefit -- most of them are static.

Playwright is not in requirements.txt: the whole test suite and a run against
static portals work without it. When it is missing, this module says exactly
what to install rather than raising an ImportError from somewhere deeper.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .fetch import USER_AGENT, _throttle

INSTALL_HINT = ("Playwright is not installed. To enable the JavaScript fallback:\n"
                "    pip install playwright && playwright install chromium\n"
                "If a browser is already on the machine, point at it with "
                "PLAYWRIGHT_CHROMIUM_PATH=/path/to/chrome")


class BrowserUnavailable(RuntimeError):
    """Playwright or a usable Chromium is not present."""


def _executable_path() -> Optional[str]:
    """Find a Chromium that actually exists.

    A pip-installed Playwright pins a browser build number and refuses to start
    if the machine carries a different one -- a common state on images that ship
    their own Chromium. An explicit path sidesteps the version pin.
    """
    explicit = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH")
    if explicit and Path(explicit).exists():
        return explicit

    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if root:
        candidate = Path(root) / "chromium"
        if candidate.exists():
            return str(candidate)
        for pattern in ("chromium-*/chrome-linux/chrome",
                        "chromium_headless_shell-*/chrome-linux/headless_shell"):
            found = sorted(Path(root).glob(pattern))
            if found:
                return str(found[-1])
    return None                      # let Playwright use its own download


def available() -> bool:
    """True when Playwright can be imported. Does not launch a browser."""
    import importlib.util
    return importlib.util.find_spec("playwright.sync_api") is not None


def render(url: str, timeout_ms: int = 30000, settle_ms: int = 1500,
           wait_for: Optional[str] = None) -> tuple[str, int]:
    """Load a page in Chromium and return its rendered HTML and HTTP status."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserUnavailable(INSTALL_HINT) from exc

    _throttle(url)                   # the same per-host courtesy as plain HTTP
    launch_kwargs = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
    executable = _executable_path()
    if executable:
        launch_kwargs["executable_path"] = executable

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_kwargs)
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                response = page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                status = response.status if response else 0
                if wait_for:
                    page.wait_for_selector(wait_for, timeout=timeout_ms)
                else:
                    page.wait_for_timeout(settle_ms)
                return page.content(), status
            finally:
                browser.close()
    except Exception as exc:         # a browser failure is never fatal to a run
        if isinstance(exc, BrowserUnavailable):
            raise
        raise BrowserUnavailable(f"Chromium could not render the page: {exc}") from exc
