"""
UNGM -- the United Nations Global Marketplace. Tier 2, and the single richest
Jordan source: UNDP, UNICEF, WFP, UNOPS, UNHCR and UNRWA all publish here.

VERIFIED AGAINST THE LIVE SITE, and both HTTP-level approaches are dead ends:

  * POST /Public/Notice/Search returned 395 bytes -- no rows, no error. The
    endpoint either moved or now requires a token the UI mints client-side.
  * GET /Public/Notice returned 141 KB of pure navigation. The derived
    selectors were menu containers; not one notice was in the markup. The
    listing is assembled client-side after load.

So this portal is rendered in a headless browser. Playwright is an OPTIONAL
dependency (requirements-browser.txt) -- when it is absent this portal fails
with an install instruction and the other twelve are unaffected.
"""

from __future__ import annotations

from . import base, browser, harvester
from .harvester import HtmlSpec

KEY = "ungm"
LISTING = "https://www.ungm.org/Public/Notice"

# A row selector to wait for before reading the DOM. A hint only: if it never
# appears the page is still read after the settle delay, so a renamed class
# degrades to a weak result the cascade can diagnose rather than a hard failure.
ROW_HINT = "div.tableRow, table tbody tr, li.notice"


def _fetch_rendered(url: str) -> str:
    """Render the listing in a headless browser and return the DOM.

    A plain fetch cannot work here -- see the module docstring. If Playwright
    is missing the error says how to install it, which is more useful than a
    portal that silently reports zero.
    """
    if not browser.available():
        raise base.PortalError(
            f"UNGM needs a headless browser: {browser.INSTALL_HINT}", url)
    return browser.render(url, wait_for=ROW_HINT)


SPEC = HtmlSpec(
    key=KEY,
    urls=[LISTING],
    # Hints only -- unverified against the live DOM.
    selectors=[
        "div.tableRow.dataRow",
        "div.tableRow",
        "tr.noticeRow",
        "table tbody tr",
    ],
    anchor_hint="/Public/Notice/",
    currency="USD",
    # The rendered listing is worldwide -- no country filter is applied before
    # it arrives, so this one is doing real work rather than defence in depth.
    filter_to_jordan=True,
    fetcher=_fetch_rendered,
    notes="JavaScript-rendered listing; needs Playwright",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
