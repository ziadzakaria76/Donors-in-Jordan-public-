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
properly ends the cap rather than raising it.

NO BROWSER ON THE REPORT PATH. The rendered listing was kept for a while as a
fallback, and it was not worth what it cost: ~400 MB of Chromium and ~30s of
install on every scheduled run, to buy a path that only runs when the endpoint
is already broken -- and which, when it does run, scrolls a WORLDWIDE listing
and stops at a cap. A portal that fails loudly is better than one that quietly
degrades to reading a fraction of the wrong list. If the endpoint breaks, UNGM
reports unavailable with the reason and the URL to check.

Playwright stays an optional dependency for --capture: capture_network() drives
a real browser to record what the page requests, which is how this endpoint was
found in the first place. Diagnosing is exactly where 400 MB earns its keep.

    GET /Public/Notice returns 141 KB of pure navigation -- the rows are not in
    the initial HTML. Still true, still why the diagnostic needs a browser.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re as _re
from collections import Counter

from bs4 import BeautifulSoup

from .. import portal_config
from ..utils import text as textutil
from . import base, browser, harvester

log = logging.getLogger(__name__)

KEY = "ungm"
# The listing page comes from portals.json so it can be corrected without a
# code change. The search endpoint is derived from it rather than declared
# separately: they are one address, and letting the file set them
# independently would allow a pair that cannot both be right.
LISTING = portal_config.primary_url(KEY)
SEARCH = (LISTING.rstrip("/") + "/Search") if LISTING else ""

# The fields this module sets in code, which portals.json therefore must not.
# The selectors and field selectors below were derived from the live DOM and
# carry their reasoning here; a value in the file would be read, accepted and
# then overridden, which looks applied and is not. The loader rejects the
# entry instead, and a test keeps this list and the file's `code_owned` in
# step.
CODE_OWNED = ("selectors", "field_selectors", "filter_to_jordan")

# From the page's own selNoticeCountry dropdown (234 options), read by
# --capture rather than guessed. UNGM uses its own numeric ids, not ISO codes,
# so there is nothing to derive this from -- it has to come from the page.
JORDAN_COUNTRY_ID = "2395"

# A row selector to wait for before reading the DOM. A hint only: if it never
# appears the page is still read after the settle delay, so a renamed class
# degrades to a weak result the cascade can diagnose rather than a hard failure.
ROW_HINT = "div.tableRow, table tbody tr, li.notice"


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


# What the last completed search displayed in each row's country cell.
# A log line was the obvious home for this and the wrong one: it is emitted at
# fetch time, which in --capture output lands a hundred lines above anything
# you are reading. A diagnostic you have to go hunting for does not get read.
LAST_COUNTRY_TALLY: Counter = Counter()


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
    LAST_COUNTRY_TALLY.clear()
    LAST_COUNTRY_TALLY.update(countries)
    # One document, so the extraction cascade sees every row at once.
    return "<html><body>" + "".join(pages) + "</body></html>"


# The URL, currency and anchor hint come from portals.json; everything below
# is CODE_OWNED and set here, next to the evidence for it.
SPEC = harvester.spec_for(
    KEY,
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
        # Anchored to .remainingDaysToDeadline, which every row has, NOT to
        # .remainingDays, which only the browser-rendered rows have. Pinning it
        # to the optional sibling worked until the search endpoint replaced the
        # scroll loop, at which point every publication date silently became
        # None -- the selector still matched nothing and nothing complained.
        #
        # This matches several spans (the counter is followed by the date, the
        # agency, the reference and the country). _apply_field_selectors takes
        # the first that parses as a date, so it reads correctly whether or not
        # .remainingDays is present.
        "posted": "span.remainingDaysToDeadline ~ span",
    },
    # Filtering happens in _is_jordan() instead: the generic text filter reads
    # the country cell, and for UNGM the majority of Jordan notices print
    # "Multiple destinations" there rather than a country name.
    filter_to_jordan=False,
    fetcher=_fetch_search,
)


# What UNGM puts in the country cell when a notice covers more than one
# country. It is a label, not a country, and it is the majority of a
# Jordan-filtered result set -- 51 of 70 on the run that found it.
_MULTI_COUNTRY_RE = _re.compile(r"multiple\s+destinations", _re.I)


def _is_jordan(record: dict) -> bool:
    """Tri-state, and the middle state is the whole point.

    THE TEXT FILTER WAS DROPPING 51 OF 70 NOTICES. We ask UNGM for
    Countries=[Jordan], it answers with 70 rows, and only 19 of them print
    "Jordan" in the country cell. The other 51 print "Multiple destinations" --
    they ARE Jordan notices, they just cover several countries and the column
    has no room to say so. Running the standard text filter over them threw
    away three quarters of the portal's Jordan work, and the count went UP at
    the same time (3 to 19), so it read as a win.

      - the row names Jordan          -> keep. The strongest evidence there is.
      - the row says "Multiple
        destinations"                 -> keep. The column CANNOT express the
                                         answer, so it is not evidence of
                                         anything; the query we sent is.
      - the row names another country -> drop. Here the column can express the
                                         answer and disagrees, so believe it.

    This is not a retreat from "never trust a source's own country filter". The
    World Bank earned that rule by IGNORING countryshortname and returning
    worldwide notices -- its filter did nothing. UNGM's demonstrably works: it
    turns thousands of worldwide notices into 70, and every row it labels with
    a single country labels it Jordan. The rule is about not letting a source's
    filter be the only check, and the single-country rows still get checked.
    What changed is that a blank answer is no longer read as a "no".
    """
    blob = " ".join(str(record.get(f) or "")
                    for f in ("title", "description", "url"))
    if textutil.mentions_jordan(record.get("title"), record.get("description"),
                                url=record.get("url")):
        return True
    return bool(_MULTI_COUNTRY_RE.search(blob))


def fetch_tenders() -> list[dict]:
    records = harvester.harvest(SPEC)
    kept = [r for r in records if _is_jordan(r)]
    # harvest() no longer filters for us, so the pre-filter total has to be
    # recorded here or the status line would read "19 (19 read)".
    base.note_scanned(len(records))
    return kept


def capture():
    return harvester.capture(SPEC)


# How many scroll passes the diagnostic makes. Small on purpose: the question
# it answers -- "what does the page ask for when it needs more rows?" -- is
# answered by the first lazy-load call, not the four hundredth.
CAPTURE_SCROLLS = 4


def capture_network() -> list[dict]:
    """The XHR/fetch calls the listing makes on load and while scrolling.

    THE ONLY THING A BROWSER IS STILL FOR HERE. Nothing in the report path
    needs one; this drives a real page purely to watch what it requests, which
    is how _fetch_search's endpoint and filter shape were found. Guessing them
    had already failed once -- POST /Public/Notice/Search "returned 395 bytes"
    went into this module's docstring as proof the endpoint was dead, and it
    was proof of a wrong request body.

    So when the endpoint next changes shape, this is the tool that says what it
    changed to, rather than leaving the next person to guess again. Playwright
    is optional and only needed to run this.
    """
    if not browser.available():
        raise base.PortalError(
            f"the UNGM network diagnostic needs a headless browser (the report "
            f"path does not): {browser.INSTALL_HINT}", LISTING)
    log: list[dict] = []
    browser.render(LISTING, wait_for=ROW_HINT, scroll_for=ROW_SELECTOR,
                   max_scrolls=CAPTURE_SCROLLS, network_log=log)
    return log
