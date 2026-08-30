"""UNDP procurement notices.

Detail pages follow view_notice.cfm?notice_id=NNNNN, which is a clean anchor-URL
pattern for the cascade's last layer.

Behind this portal, UNDP's Quantum supplier portal also serves UNFPA, UN Women,
UNCDF and UNV, so those agencies' notices surface here too.

THE SELECTORS BELOW ARE NO LONGER GUESSES. They were, and this docstring said
so; `--capture all` on 2026-08-30 read the live page and they are now what it
reported. See the class attribute for the evidence and for what it cost to
leave them unset.
"""

from __future__ import annotations

import re

from .base import HtmlPortal

BASE = "https://procurement-notices.undp.org"


class UndpPortal(HtmlPortal):
    name = "undp"
    label = "UNDP"
    url = BASE + "/"
    anchor_pattern = r"view_notice\.cfm\?notice_id=\d+"
    # READ OFF THE LIVE PAGE, not guessed -- the previous value was None with
    # the note "guesses removed rather than shipped unverified", and this is
    # what the capture of 2026-08-30 (Actions run 33287873872) reported:
    #
    #   a.vacanciesTableLink x572, a.vacanciesTable__row x572
    #
    # The run was reading SIX of those 572. Every row carries its own country
    # and region in its class list --
    #
    #   34->34 q=0.44 a.country_4.region_RAS.vacanciesTableLink.vacanciesTable__row
    #   21->21 q=0.42 a.country_5.region_RAS.vacanciesTableLink.vacanciesTable__row
    #   49->49 q=0.40 a.country_5.region_RER.vacanciesTableLink.vacanciesTable__row
    #
    # -- so grouping by class signature shatters one listing into dozens of
    # per-country fragments, the largest 49, none of them reaching the 0.45
    # threshold. A six-row structural group won at 0.55 instead.
    #
    # That is the same shape of failure as UNGM's, arrived at from the opposite
    # direction: there one group beat the right one, here the right group never
    # formed. Both are answered by naming the row.
    #
    # The title is deliberately NOT pinned. The page holds
    # div.vacanciesTable__cell x3438 -- six per row -- and which one is the
    # title is not established by anything in that capture. Guessing it is what
    # the note this replaces was warning about; the next capture prints the
    # cells and settles it.
    selectors = {
        "row": "a.vacanciesTableLink",
        # The first cell. Its own label is rendered inside it, so the text
        # arrives as "Title Supply and Delivery of ..." -- see row_to_record.
        "title": "div.vacanciesTable__cell",
    }

    # Each cell carries its column label as an inline element, so a cell's text
    # begins with the label. The capture of 2026-08-30 printed one row in full:
    #
    #   [0] Title Supply and Delivery of Postal Fleet Vehicles for the GAMPOST
    #   [1] Ref No UNDP-GMB-00607-3
    #   [2] UNDP Office/Country UNDP-GMB/GAMBIA
    #   [3] Process RFQ - Request for quotation
    #   [4] Deadline 01-Sep-26 09:20 AM (New York time)
    #   [5] Posted 29-Aug-26
    _TITLE_LABEL = re.compile(r"^\s*Title\s+")

    # The office/country cell, which is the country UNDP itself assigns to the
    # notice. Written as ISO-ish code then name: UNDP-GMB/GAMBIA, UNDP-SYR/SYRIA.
    _OFFICE_COUNTRY = re.compile(r"UNDP\s+Office/Country\s+\S*?/(\w[\w\s]*)")

    def row_to_record(self, row, page_url: str) -> dict:
        record = super().row_to_record(row, page_url)

        # THE LABEL IS PART OF THE CELL'S TEXT. Every UNDP entry reached the
        # report as "Title Providing Health Facilities with Renewable Energy
        # Ref No UNDP-SYR-..." -- the column heading, then the notice, then the
        # next column. Cosmetically that is a bad title; mechanically it is a
        # duplicate, because _dedupe_key is title|closing and UNGM lists the
        # same notices under their real names. Once deadlines started parsing
        # the two rows agreed on the date and differed only by the word
        # "Title", so the run of 2026-08-30 carried both:
        #
        #   1. Rehabilitation of Schools & Health Centers ...  ungm | 08-Sep-2026
        #   2. Title Rehabilitation of Schools & Health Cen...  undp | 08-Sep-2026
        #
        # Two of the top ten were one tender counted twice.
        title = self._TITLE_LABEL.sub("", record.get("title") or "").strip()
        if title:
            record["title"] = title

        # UNDP NAMES THE COUNTRY ITSELF, in its office/country column, and the
        # gate was reading prose instead: 8 of 572 rows were kept on a text
        # match. A field the source states is better evidence than a word found
        # in a description, and it lets the gate reject the other 564 for the
        # reason they should be rejected rather than for silence.
        match = self._OFFICE_COUNTRY.search(row.text or "")
        if match and not record.get("country"):
            record["country"] = match.group(1).strip()
        return record
