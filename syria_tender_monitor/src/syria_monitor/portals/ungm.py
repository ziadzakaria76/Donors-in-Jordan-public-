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

import re
from datetime import date

from ..dates import CLOSING_LABELS, find_labelled_date
from .base import HtmlPortal

# What UNGM prints in the country cell when a notice covers several countries.
# It is a label, not a country -- see row_to_record().
MULTI_DESTINATION_RE = re.compile(r"multiple\s+destinations", re.I)

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
            response = self.fetcher.post(
                url, json=self.search_body(),
                headers={"X-Requested-With": "XMLHttpRequest", "Referer": NOTICE_PAGE})
            return response.text, response.status
        response = self.fetcher.get(url)     # the dropdown page, for --capture
        return response.text, response.status

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
        deadline = find_labelled_date(row.text, CLOSING_LABELS)
        if deadline:
            record["closing_date"] = deadline.isoformat()

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
        if not record.get("country") and MULTI_DESTINATION_RE.search(row.text or ""):
            record["country"] = self.profile.get("name", "")
        return record
