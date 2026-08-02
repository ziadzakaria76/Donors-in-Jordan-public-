"""
UNGM -- the United Nations Global Marketplace. Tier 2, and the single richest
Jordan source: UNDP, UNICEF, WFP, UNOPS, UNHCR and UNRWA all publish here.

The public listing is JavaScript-driven, so fetching /Public/Notice returns a
shell. The UI itself calls a POST search endpoint that returns rendered rows,
which is what this module targets. If that endpoint changes, the HTML fallback
below still runs through the cascade rather than the portal going dark.

VERIFICATION STATUS: never run against the live site. The POST endpoint and its
payload shape are the least certain part of this codebase -- confirm with
`python run.py --capture ungm` before trusting this portal.
"""

from __future__ import annotations

from . import base, harvester
from .harvester import HtmlSpec

KEY = "ungm"
LISTING = "https://www.ungm.org/Public/Notice"
SEARCH = "https://www.ungm.org/Public/Notice/Search"

# UNGM's own country id for Jordan. If results come back worldwide, this is the
# value to check first.
JORDAN_COUNTRY_ID = 113

_PAYLOAD = {
    "PageIndex": 0,
    "PageSize": 100,
    "Title": "",
    "Description": "",
    "Reference": "",
    "PublishedFrom": "",
    "PublishedTo": "",
    "DeadlineFrom": "",
    "DeadlineTo": "",
    "Countries": [JORDAN_COUNTRY_ID],
    "Agencies": [],
    "UNSPSCs": [],
    "NoticeTypes": [],
    "SortField": "DatePublished",
    "SortAscending": False,
    "isPicker": False,
}


def _fetch_search_html(url: str) -> str:
    """POST to the search endpoint and return its HTML fragment.

    Falls back to a plain GET of the listing page so that --capture still has
    something to show, and so the cascade can diagnose a JavaScript shell
    rather than the portal reporting a bare transport error.
    """
    if url == SEARCH:
        try:
            response = base._request(
                "POST", SEARCH, json=_PAYLOAD,
                headers={"X-Requested-With": "XMLHttpRequest",
                         "Referer": LISTING,
                         "Accept": "text/html, */*; q=0.01"},
            )
            response.encoding = response.encoding or "utf-8"
            return response.text
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            raise base.PortalError(
                f"POST search endpoint failed ({type(exc).__name__}: {exc}). "
                f"The listing is JavaScript-driven, so a plain GET returns an "
                f"empty shell; confirm the endpoint with --capture.", SEARCH) from exc
    return base.fetch(url)


SPEC = HtmlSpec(
    key=KEY,
    urls=[SEARCH, LISTING],
    # Hints only -- unverified against the live DOM.
    selectors=[
        "div.tableRow.dataRow",
        "div.tableRow",
        "tr.noticeRow",
        "table tbody tr",
    ],
    anchor_hint="/Public/Notice/",
    currency="USD",
    # The search is already filtered to Jordan, but the HTML fallback is not,
    # and a silently ignored country filter would flood the report.
    filter_to_jordan=True,
    fetcher=_fetch_search_html,
    notes="POST search endpoint; JS-driven listing page",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
