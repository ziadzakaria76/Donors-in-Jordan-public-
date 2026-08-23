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

2. The POST body below is a documented skeleton, NOT a verified capture. It
   must be replaced field-for-field from a real network trace before it can be
   trusted. A previous reconstruction of this request from documentation is
   what convinced everyone the endpoint was dead.

The UI's own IsActive and DeadlineFrom fields are sent because they are what
the UI sends -- but every deadline is re-checked downstream anyway. A source's
own filter is a hint, never a guarantee. Note also that the page size the UI
asks for is not necessarily the one that governs paging: trust what page one
returns.
r"""

from __future__ import annotations

from datetime import date

from ..dates import CLOSING_LABELS, find_labelled_date
from .base import HtmlPortal

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
        """UNGM search POST body.

        SKELETON -- replace field-for-field from a --capture network trace.
        """
        return {
            "PageIndex": page,
            "PageSize": int(self.cfg.get("page_size", 100)),
            "Title": "",
            "Description": "",
            "Reference": "",
            "PublishedFrom": "",
            "PublishedTo": "",
            "DeadlineFrom": date.today().strftime("%d-%b-%Y"),
            "DeadlineTo": "",
            "Countries": [int(self.cfg["country_id"])],
            "NoticeTypes": [],
            "UNSPSCs": [],
            "Agencies": [],
            "IsActive": True,
            "SortField": "DeadlineUTC",
            "SortAscending": True,
        }

    def pages(self):
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
        html, status = self.fetch_page("search", SEARCH_ENDPOINT)
        result = self.extract_page(html, SEARCH_ENDPOINT, status)
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
        return record
