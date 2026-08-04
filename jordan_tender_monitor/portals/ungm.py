"""
UNGM -- the United Nations Global Marketplace. Tier 2, and the single richest
Jordan source: UNDP, UNICEF, WFP, UNOPS, UNHCR and UNRWA all publish here.

THE SEARCH ENDPOINT WORKS. An earlier note in this module said otherwise --
"POST /Public/Notice/Search returned 395 bytes ... the endpoint either moved or
now requires a token the UI mints client-side" -- and that was wrong on both
counts. It has not moved and it needs no token. The earlier attempt sent the
wrong body and read the reply as JSON; the endpoint takes a specific JSON
filter and answers with an HTML fragment.

That mistaken conclusion is what bought the headless browser and the scroll
loop, and it cost more than the browser. The scroll loop was driving this very
endpoint by hand: a --capture network trace showed five POSTs with PageIndex
running 0,1,2,3,4 -- one per scroll pass. Forty passes read 615 rows of a
WORLDWIDE listing and were still growing, to keep the three that were Jordan.

The endpoint takes Countries, so the listing we read is Jordan's, and paging it
properly ends the cap rather than raising it. The browser remains as a fallback
and is no longer on the fast path.

    GET /Public/Notice returns 141 KB of pure navigation -- the rows are not in
    the initial HTML. That part of the old note was correct, and it is why the
    fallback still needs a browser.
"""

from __future__ import annotations

import datetime as _dt
import logging

from bs4 import BeautifulSoup

from . import base, browser, harvester
from .harvester import HtmlSpec

log = logging.getLogger(__name__)

KEY = "ungm"
LISTING = "https://www.ungm.org/Public/Notice"
SEARCH = "https://www.ungm.org/Public/Notice/Search"

# From the page's own selNoticeCountry dropdown (234 options), read by
# --capture rather than guessed. UNGM uses its own numeric ids, not ISO codes,
# so there is nothing to derive this from -- it has to come from the page.
JORDAN_COUNTRY_ID = "2395"

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

# What the UI itself asks for. See _fetch_search(): the value that actually
# governs paging is the one page one returns, not this one.
PAGE_SIZE = 15

ROW_SELECTOR = "div.dataRow.notice-table"


# Pages of Jordan-only results, not pages of the world. Jordan runs to a
# couple of dozen open notices, so this is headroom rather than a limit -- but
# it is still logged when reached, because a cap that is hit silently turns
# "read everything" and "read the first N" into the same output.
MAX_PAGES = 40


def _search_body(page_index: int, page_size: int) -> dict:
    """The filter the UNGM UI itself posts, with Countries filled in.

    Copied field-for-field from a --capture network trace rather than
    reconstructed from the docs, because the last reconstruction of this
    request is what convinced everyone the endpoint was dead.

    IsActive + DeadlineFrom=today are the site's own "currently open" filter.
    They are kept because they are what the UI sends, not relied upon: the
    pipeline re-checks every deadline downstream, on the standing rule that a
    source's own filter is a hint and never a guarantee.
    """
    today = _dt.date.today().strftime("%d-%b-%Y")
    return {
        "PageIndex": page_index,
        "PageSize": page_size,
        "Title": "", "Description": "", "Reference": "",
        "PublishedFrom": "", "PublishedTo": today,
        "DeadlineFrom": today, "DeadlineTo": "",
        "Countries": [JORDAN_COUNTRY_ID],
        "Agencies": [], "UNSPSCs": [], "NoticeTypes": [],
        "SortField": "Deadline", "SortAscending": True,
        "isPicker": False, "IsSustainable": False, "IsActive": True,
        "NoticeDisplayType": None,
        "NoticeSearchTotalLabelId": "noticeSearchTotal",
        "TypeOfCompetitions": [],
    }


def _row_count(fragment: str) -> int:
    return len(BeautifulSoup(fragment, "html.parser").select(ROW_SELECTOR))


def _country_cells(fragment: str) -> list[str]:
    """The country each row DISPLAYS -- the last span, per the live row anatomy.

    We ask UNGM for Jordan and it answers with rows whose displayed country is
    often something else. That gap is the whole question about this portal: it
    is either UNGM's filter being broader than its country column (in which
    case the downstream text filter is right to drop them) or notices that
    cover Jordan among several countries (in which case dropping them loses
    real work). Counting the values is what tells the two apart, so the run
    says it out loud rather than leaving a bare "50 not Jordan" to be guessed at.
    """
    cells = []
    for row in BeautifulSoup(fragment, "html.parser").select(ROW_SELECTOR):
        spans = row.find_all("span")
        cells.append(spans[-1].get_text(" ", strip=True) if spans else "")
    return cells


def _fetch_search(url: str) -> str:
    """Page the search endpoint and return every page's markup, concatenated.

    THE PAGE SIZE IS MEASURED, NOT ASSUMED. Asking for 100 and receiving 15
    because the server caps it would make every page look short, and "short
    page" is the signal this loop uses for "the listing has ended" -- so an
    unhonoured PageSize would stop the read after one page and call it
    complete. Whatever page one returns IS the page size; that is the only
    number that cannot be wrong.
    """
    base.warm_session(LISTING)

    pages: list[str] = []
    countries: list[str] = []
    stride = 0
    total = 0
    for index in range(MAX_PAGES):
        fragment = base.post_text(SEARCH, _search_body(index, PAGE_SIZE))
        found = _row_count(fragment)
        if not found:
            break
        pages.append(fragment)
        countries.extend(_country_cells(fragment))
        total += found
        if stride == 0:
            stride = found
        if found < stride:
            break
    else:
        log.warning(
            "ungm: read %d notices across the %d-page cap and the last page "
            "was still full -- there are probably more", total, MAX_PAGES)

    if not pages:
        raise base.PortalError(
            "the search endpoint answered but returned no notice rows -- the "
            "filter shape or the row markup may have changed; run "
            "--capture ungm to see what it sends now", SEARCH)

    log.info("ungm: %d notices over %d page(s) of %d", total, len(pages), stride)
    if countries:
        from collections import Counter
        tally = Counter(countries)
        log.info("ungm: countries displayed by a Jordan-filtered search: %s",
                 ", ".join(f"{name or '(blank)'}={count}"
                           for name, count in tally.most_common(12)))
    # One document, so the extraction cascade sees every row at once.
    return "<html><body>" + "".join(pages) + "</body></html>"


def _fetch_rendered(url: str) -> str:
    """Fallback: render the listing in a headless browser and scroll it.

    Kept because the search endpoint is undocumented and could change shape
    without notice, and a portal that goes dark is worse than a slow one. It is
    genuinely worse than the endpoint, though -- it scrolls a WORLDWIDE listing
    and stops at a cap -- so which path ran is logged rather than left to be
    inferred from timing.
    """
    if not browser.available():
        raise base.PortalError(
            f"UNGM needs a headless browser: {browser.INSTALL_HINT}", url)
    return browser.render(url, wait_for=ROW_HINT,
                          scroll_for=ROW_SELECTOR, max_scrolls=MAX_SCROLLS)


def _fetch(url: str) -> str:
    """The search endpoint, falling back to the browser if it ever stops working."""
    try:
        return _fetch_search(url)
    except base.PortalError as exc:
        if browser.available():
            log.warning("ungm: the search endpoint failed (%s); falling back "
                        "to scrolling the rendered listing, which reads the "
                        "WORLDWIDE list and stops at a cap", exc.reason)
            return _fetch_rendered(url)
        # Both paths gone. Name BOTH, because either one alone sends you after
        # the wrong problem: the endpoint error alone hides that a browser
        # would have rescued the run, and the install hint alone hides that the
        # endpoint -- the thing worth fixing -- has broken.
        raise base.PortalError(
            f"the search endpoint failed ({exc.reason}) and the browser "
            f"fallback is unavailable: {browser.INSTALL_HINT}", url) from exc


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
    fetcher=_fetch,
    notes="Jordan-filtered search endpoint; browser fallback",
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
