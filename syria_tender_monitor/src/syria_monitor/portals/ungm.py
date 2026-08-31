"""UNGM -- the richest single source for this country by a wide margin.

Covers UNDP, UNICEF, WFP, UNOPS, UNHCR, UNRWA, WHO and IOM. The UI is
JavaScript-driven but calls a POST search endpoint that works over plain HTTP.

TWO THINGS THAT MUST BE READ OFF THE LIVE SITE, NOT GUESSED
-----------------------------------------------------------
1. UNGM does not use ISO country codes. It uses its own numeric ids (Jordan is
   2395, established against the live API in another build of this system).
   There is no table to derive one from and no way to guess it: the id has to
   be read out of the selNoticeCountry dropdown on the live page, which carries
   234 options. Run `--capture ungm` and read it off the page.

   This module therefore REFUSES TO RUN with country_id unset rather than
   sending a guess. UNGM is the richest source here, so a wrong id is the
   difference between the build's best portal working and it silently
   returning nothing.

2. The POST body below WAS a documented skeleton and is no longer one: it was
   replaced field-for-field from a real network trace on 2026-08-30, and the
   skeleton had been wrong in six places. See search_body(). A reconstruction
   of this request from documentation is what convinced everyone the endpoint
   was dead; it was proof of a wrong body, not a dead endpoint.

The UI's own IsActive and DeadlineFrom fields are sent because they are what
the UI sends -- but every deadline is re-checked downstream anyway. A source's
own filter is a hint, never a guarantee. Note also that the page size the UI
asks for is not necessarily the one that governs paging: trust what page one
returns.
r"""

from __future__ import annotations

import logging
import re
from datetime import date

from ..dates import CLOSING_LABELS, find_labelled_date, parse_date
from .base import HtmlPortal

log = logging.getLogger(__name__)

# Pages of THIS COUNTRY's results, not pages of the world, so this is headroom
# rather than a limit -- but it is still reported when reached, because a cap
# that is hit silently makes "read everything" and "read the first N" produce
# the same output with no way to tell them apart.
MAX_PAGES = 40

# What UNGM prints in the country cell when a notice covers several countries.
# It is a label, not a country -- see row_to_record().
MULTI_DESTINATION_RE = re.compile(r"multiple\s+destinations", re.I)

# The date at the front of a cell, ignoring whatever trails it. UNGM appends a
# time, a timezone and a fractional countdown to its deadline cell.
_LEADING_DATE = re.compile(
    r"\b(\d{1,2}[-/\s][A-Za-z]{3,9}[-/\s]\d{4}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}[-/]\d{1,2}[-/]\d{4})")


def _cell_date(value):
    """The date a deadline cell starts with, or None."""
    match = _LEADING_DATE.search(str(value or ""))
    return parse_date(match.group(1)) if match else None


BASE = "https://www.ungm.org"
NOTICE_PAGE = f"{BASE}/Public/Notice"
SEARCH_ENDPOINT = f"{BASE}/Public/Notice/Search"

# The dropdown to read the numeric country id out of, via --capture.
COUNTRY_SELECT_ID = "selNoticeCountry"


class UngmPortal(HtmlPortal):
    name = "ungm"
    label = "UNGM"
    url = NOTICE_PAGE
    anchor_pattern = r"/Public/Notice/\d+"

    # DERIVED FROM THE LIVE DOM, and the reason they are here rather than left
    # to the class-independent layers is a regression they caused.
    #
    # Reading one page, the cascade picked div.dataRow.notice-table.tableRow and
    # scored it 0.91. Reading six, the same page shape scored 0.70 and LOST to
    # div.deadline.resultInfo1.tableCell at 0.83 -- a group of 87 deadline
    # CELLS, one per row. Extraction then reported 87 rows and the run kept
    # none of them, because a cell holding a date carries no country for the
    # gate to read:
    #
    #     UNGM: ok -- 0 kept of 87 fetched      (was 7 kept of 15)
    #
    # Quality is a heuristic over rows the layer already built; it cannot know
    # that one candidate is the notice and the other is a column of it. Both
    # are 87 well-formed rows. Naming the row settles it and costs nothing --
    # if the class ever disappears the selector matches nothing, the layer
    # yields no rows, and the cascade carries on to the layers below.
    #
    # Confirmed in the capture of 2026-08-30 (Actions run 33287077057):
    #   div.dataRow x87, div.notice-table x87   -- one per notice
    #   span.ungm-title.ungm-title--small x87   -- the title is a SPAN
    #
    # That last line is why the anchor rule alone could not fix the titles: no
    # anchor in the row is both navigable and texted, so the lookup falls back
    # and a.save-notice-button (href="#", x174) wins on its label. The title was
    # never in an anchor to begin with.
    selectors = {
        "row": "div.dataRow.notice-table",
        "title": "span.ungm-title",
        # div.deadline.resultInfo1.tableCell x87 in the same capture -- one per
        # notice, and the group that outscored the notices themselves. See
        # row_to_record() for why the cell is re-parsed rather than used as-is.
        "deadline": "div.deadline",
    }

    def unavailable_reason(self):
        if not self.cfg.get("country_id"):
            return ("portals.ungm.country_id is not set. UNGM uses its own numeric "
                    "country ids, not ISO codes -- read this country's id out of the "
                    f"{COUNTRY_SELECT_ID} dropdown with `--capture ungm` and set it in "
                    "config.yml. Refusing to guess: a wrong id returns nothing, silently.")
        return None

    def search_body(self, page: int = 0) -> dict:
        """UNGM search POST body, taken from a real request the UI made.

        NO LONGER A SKELETON. Recorded on 2026-08-30 by driving the live
        listing in Chromium and watching what it asked for -- Actions run
        33282804658, five POSTs to this endpoint, HTTP 200, ~95 KB each. The
        field names, the field order and the literal values below are that
        request, not a reconstruction of it.

        That distinction has already cost this project once. The previous
        skeleton was wrong in six places, and a wrong body does not error: it
        returns a short response that reads exactly like "there is nothing for
        this country". The note that went into a sibling module -- POST
        /Public/Notice/Search "returned 395 bytes", filed as proof the endpoint
        was dead -- was proof of a wrong request body.

        What the skeleton got wrong, since knowing which guesses failed is
        worth more than the corrected list:

          SortField     "DeadlineUTC" -> "Deadline". The likeliest culprit of
                        the three: an unrecognised sort field is exactly the
                        sort of input a search API rejects wholesale.
          PageSize      100 -> 15. The UI asks for 15. Whether UNGM caps or
                        refuses larger pages is UNTESTED -- 15 is simply the
                        only value observed to work.
          PublishedTo   "" -> today. The UI bounds the upper end rather than
                        leaving it open.
          five fields   isPicker, IsSustainable, NoticeDisplayType,
                        NoticeSearchTotalLabelId and TypeOfCompetitions were
                        absent entirely.

        `isPicker` really is lower-cased where its neighbours are not. That is
        UNGM's spelling, it is what the server was sent, and correcting it to
        `IsPicker` would be reintroducing a guess.

        TWO PARAMETERISED VALUES, and only two: the page, and the country. The
        capture was of an unfiltered listing, so the UI sent `"Countries": []`.
        It therefore proves the field name and that it takes an array -- it
        does NOT prove that [2490] narrows the result to Syria. The first
        `--capture ungm` against this body is what settles that, by whether the
        rows it returns say Syria.
        """
        today = date.today().strftime("%d-%b-%Y")
        return {
            "PageIndex": page,
            "PageSize": int(self.cfg.get("page_size", 15)),
            "Title": "",
            "Description": "",
            "Reference": "",
            "PublishedFrom": "",
            "PublishedTo": today,
            "DeadlineFrom": today,
            "DeadlineTo": "",
            "Countries": [int(self.cfg["country_id"])],
            "Agencies": [],
            "UNSPSCs": [],
            "NoticeTypes": [],
            "SortField": "Deadline",
            "SortAscending": True,
            "isPicker": False,
            "IsSustainable": False,
            "IsActive": True,
            "NoticeDisplayType": None,
            "NoticeSearchTotalLabelId": "noticeSearchTotal",
            "TypeOfCompetitions": [],
        }

    def pages(self):
        # Without a country id the search body cannot be built -- but the
        # dropdown page is precisely where that id is read from, so capture must
        # still be able to fetch it. Refusing both would make the documented way
        # of obtaining the id impossible to follow.
        if not self.cfg.get("country_id"):
            return [("dropdown", NOTICE_PAGE)]
        return [("search", SEARCH_ENDPOINT), ("dropdown", NOTICE_PAGE)]

    def fetch_page(self, label: str, url: str) -> tuple[str, int]:
        if label == "search":
            return self._fetch_search(url)
        response = self.fetcher.get(url)     # the dropdown page, for --capture
        return response.text, response.status

    def _post_search(self, url: str, page: int):
        return self.fetcher.post(
            url, json=self.search_body(page),
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": NOTICE_PAGE})

    def _fetch_search(self, url: str) -> tuple[str, int]:
        """Page the search endpoint; return every page concatenated.

        ONLY PAGE ONE WAS EVER READ. The capture of 2026-08-30 returned exactly
        15 rows against a PageSize of 15 -- a result the same size as the page
        is the standard signal that there is another page, and there was no
        loop to follow it. Whatever this country has beyond the first fifteen
        open notices has never reached a report, and nothing said so: a short
        read and a quiet week produce the same output.

        THE PAGE SIZE IS MEASURED, NOT ASSUMED. Asking for 15 and receiving 10
        because the server caps it would make every page look short, and "short
        page" is this loop's signal that the listing has ended -- so an
        unhonoured PageSize would stop the read after one page and call it
        complete. Whatever page one returns IS the stride; it is the only
        number here that cannot be wrong.

        Rows are counted with the extraction cascade rather than a row selector,
        so the stop condition does not rest on a class name that UNGM is free to
        rename. A rename would then cost a wrong row count in one place instead
        of silently ending the read at page one.

        A REPEATED PAGE ENDS THE READ. An endpoint that ignores PageIndex and
        serves page one forever satisfies "the page was full" every time, so the
        only thing between that and forty identical fetches is the cap -- and
        the listing would then be concatenated forty times over, turning one
        notice into forty rows. The full-page condition cannot tell that apart
        from a genuine long listing; comparing the fetched text can.
        """
        fragments: list[str] = []
        first_text, status = "", 200
        stride = 0
        previous = None

        for index in range(MAX_PAGES):
            response = self._post_search(url, index)
            status = response.status
            if index == 0:
                first_text = response.text
            if not response.ok:
                # Hand the failing response back whole: page_result() and the
                # diagnostics downstream are what turn a bad status into a
                # readable reason, and they need the body to do it.
                return response.text, status

            if response.text == previous:
                log.warning(
                    "ungm: page %d was byte-identical to page %d -- the endpoint "
                    "is not honouring PageIndex; stopping rather than counting "
                    "the same notices twice", index, index - 1)
                break
            previous = response.text

            found = len(self.extract_page(response.text, url, status).rows)
            if not found:
                break
            fragments.append(response.text)
            if stride == 0:
                stride = found
            if found < stride:
                break
        else:
            log.warning(
                "ungm: read %d notices across the %d-page cap and the last page "
                "was still full -- there are probably more",
                stride * MAX_PAGES, MAX_PAGES)

        if not fragments:
            # Nothing parsed. Return page one unchanged so the cascade can say
            # why, rather than an empty string that discards the evidence.
            return first_text, status

        # One document, so the cascade sees every row at once and scores the
        # whole listing rather than each page separately.
        return "<html><body>" + "".join(fragments) + "</body></html>", status

    def fetch_tenders(self) -> list[dict]:
        # Only the search endpoint is fetched for a run; the dropdown page in
        # pages() exists for --capture. page_result() applies the same browser
        # escalation the other HTML portals get -- UNGM's UI is JavaScript-driven,
        # so if the POST endpoint ever stops answering over plain HTTP, this is
        # the path that keeps it working.
        result = self.page_result("search", SEARCH_ENDPOINT)
        self._winning_layer, self._winning_quality = result.layer, result.quality
        if not result.rows:
            raise RuntimeError(result.diagnosis or "UNGM search returned no rows")
        return [self.row_to_record(row, SEARCH_ENDPOINT) for row in result.rows]

    def row_to_record(self, row, page_url: str) -> dict:
        record = super().row_to_record(row, page_url)
        # UNGM writes a relative countdown ("Expires in 38 days") between the
        # real deadline and the publication date. Taking the next date-shaped
        # text after a closing label lands on the publication date, every notice
        # then carries a deadline months earlier than its real one, and a
        # deadline in the past is dropped as closed -- so the portal's entire
        # open pipeline disappears with nothing to indicate anything went wrong.
        # EVERY LINE OF THE REPORT SAID "closes not published". UNGM prints its
        # column labels in the table header, not in the rows, so there is no
        # "Deadline:" in a row's text for find_labelled_date to anchor to, and
        # it returned None for all 87 notices. The cell itself did not help
        # either: it reads
        #
        #     30-Aug-2026 08:00 (GMT -4.00) 0.413660439452546
        #
        # and parse_date refuses the whole string -- the trailing countdown
        # fraction is not part of any date. So the leading date is taken out of
        # the deadline cell and parsed on its own.
        #
        # This is not cosmetic. With no closing date, `drop_expired: true` has
        # nothing to test, so a closed tender is reported as open -- the report
        # was carrying them silently.
        deadline = _cell_date(record.get("closing_date")) or find_labelled_date(
            row.text, CLOSING_LABELS)
        if deadline:
            record["closing_date"] = deadline.isoformat()
        elif record.get("closing_date"):
            # A cell that is present but unparseable must not reach the report
            # as a date-shaped string that nothing downstream can read.
            record["closing_date"] = None

        # "MULTIPLE DESTINATIONS" IS NOT ANOTHER COUNTRY. It is UNGM saying the
        # column has no room for the answer, and on a country-filtered search it
        # is the majority of the result set: the live run of 2026-08-30 read 15
        # rows, 7 naming this country and 8 labelled this way, and kept 7. The
        # eight were dropped for "no evidence" -- their row text never says
        # Syria, because the cell that would have said it says this instead.
        #
        # The evidence those rows do have is the request that produced them. We
        # sent Countries=[country_id] and UNGM answered with these; a label that
        # cannot express a country is not the source disagreeing with us.
        #
        # This is not a retreat from "a source's own filter is a hint, never a
        # guarantee". Rows that name some OTHER country still say so and are
        # still rejected on that -- there the column CAN express the answer and
        # does. What changes is that a blank answer stops being read as "no".
        #
        # The sibling Jordan monitor reached this the expensive way: its text
        # filter was discarding 51 of 70 notices, and the kept count ROSE when
        # the bug was introduced (3 to 19), so it read as an improvement.
        #
        # DECLARED, because the gate cannot tell this apart from a country the
        # page actually printed. The live run of 2026-08-31 kept 85 of 85 rows,
        # and the report's third and sixth entries were a "Global and Regional"
        # child-wasting study and an IMO greenhouse-gas study -- neither of them
        # this country's work. Whether to keep admitting those is a judgement
        # about recall against precision; reporting the count is not.
        if not record.get("country") and MULTI_DESTINATION_RE.search(row.text or ""):
            record["country"] = self.profile.get("name", "")
            record["country_inferred"] = "ungm_multiple_destinations"
        return record
