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


# The listing lazily loads as you scroll. VERIFIED: --capture found NO
# pagination control anywhere in the rendered DOM -- the only candidates were a
# jQuery datepicker's month arrows and its day cells, which read as "Prev",
# "Next", "1", "2", "3". There is no page two to follow; there is more list.
#
# 40 passes at 15 rows a page is roughly 600 notices, which is the whole open
# pipeline rather than a sample. The cap is logged when it is reached, because
# "read everything" and "read the first N" must not look alike.
MAX_SCROLLS = 40

ROW_SELECTOR = "div.dataRow.notice-table"


def _fetch_rendered(url: str) -> str:
    """Render the listing in a headless browser and return the DOM.

    A plain fetch cannot work here -- see the module docstring. If Playwright
    is missing the error says how to install it, which is more useful than a
    portal that silently reports zero.
    """
    if not browser.available():
        raise base.PortalError(
            f"UNGM needs a headless browser: {browser.INSTALL_HINT}", url)
    return browser.render(url, wait_for=ROW_HINT,
                          scroll_for=ROW_SELECTOR, max_scrolls=MAX_SCROLLS)


SPEC = HtmlSpec(
    key=KEY,
    urls=[LISTING],
    # DERIVED FROM THE RENDERED DOM, not guessed: --capture on the browser
    # output reported div.dataRow.notice-table with 15 matching blocks, and the
    # structural and anchor layers independently found the same 15 rows.
    #
    # "table tbody tr" is deliberately NOT in this list. It matched six rows on
    # the live page -- the Su/Mo/Tu/We/Th/Fr/Sa cells of the date-picker widget.
    # An over-broad selector runs before the class-independent layers and would
    # short-circuit the one that actually works; this is the exact failure the
    # quality gate exists to catch, and there is no reason to hand it one.
    selectors=[
        "div.dataRow.notice-table",
        "div.tableRow.dataRow",
        "div.tableRow",
        "tr.noticeRow",
    ],
    # DERIVED FROM THE LIVE ROW ANATOMY, not guessed. The row's columns are
    # unlabelled sibling spans, in this order:
    #
    #     span                          '03-Aug-2026 22:59 (GMT -6.00)'
    #     span.remainingDaysToDeadline  '0.234606972739583'
    #     span.remainingDays            'Expires within 24 hours'
    #     span                          '20-Jul-2026'
    #
    # Nothing in the markup says which date is which, so they cannot be read by
    # inference: "the first date is the deadline" is true here and false on GIZ,
    # and a wrong deadline silently drops an open tender. Being siblings, they
    # ARE addressable -- the deadline is the span immediately before the
    # remaining-days counter, and the publication date the one after it.
    field_selectors={
        "title": "span.ungm-title",
        "closing": "span:has(+ span.remainingDaysToDeadline)",
        # "~" rather than "+": the adjacent-sibling form worked on the fixture
        # and matched nothing on the live page, so the publication date came
        # back empty while the deadline read correctly. The published span is
        # the first span AFTER the counter, but not necessarily the very next
        # node. The deadline uses ":has(+ ...)" and does work live, which is
        # what matters most -- a missing publication date costs ranking
        # precision; a missing deadline would drop the notice.
        "posted": "span.remainingDays ~ span",
    },
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


# How many scroll passes the diagnostic makes. Small on purpose: the question
# it answers -- "what does the page ask for when it needs more rows?" -- is
# answered by the first lazy-load call, not the four hundredth.
CAPTURE_SCROLLS = 4


def capture_network() -> list[dict]:
    """The XHR/fetch calls the listing makes on load and while scrolling.

    Scrolling is a workaround for not knowing the endpoint. 40 passes read 615
    rows and the listing was still growing, so the cap was truncating a
    worldwide list that we then filter down to a handful of Jordan notices --
    reading thousands of rows to keep three. If the page fetches its rows from
    an endpoint that takes a page number or a country, calling it directly
    replaces the whole scroll loop.

    Guessing that endpoint has already failed here once (POST
    /Public/Notice/Search returned 395 bytes), so this reports what the UI
    actually calls rather than what it plausibly might.
    """
    if not browser.available():
        raise base.PortalError(
            f"UNGM needs a headless browser: {browser.INSTALL_HINT}", LISTING)
    log: list[dict] = []
    browser.render(LISTING, wait_for=ROW_HINT, scroll_for=ROW_SELECTOR,
                   max_scrolls=CAPTURE_SCROLLS, network_log=log)
    return log
