"""
EBRD -- European Bank for Reconstruction and Development. Tier 2.

Two sources: the notices page on ebrd.com, and ECEPP, which is where the
tender documents and many of the consultancy assignments actually live. Either
one failing is tolerated as long as the other works.

VERIFICATION STATUS: never run against the live site; selectors unverified.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec

KEY = "ebrd"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        "https://www.ebrd.com/home/work-with-us/project-procurement/procurement-notices.html",
        "https://ecepp.ebrd.com/delta/noticeSearchResults.html",
    ],
    # SELECTOR HINTS ONLY -- written without access to the live pages, which
    # were blocked from the build environment. If a hint is wrong the quality
    # gate rejects it and a class-independent layer takes over. Confirm with:
    #     python run.py --capture ebrd
    selectors=[
        "div.procurement-notice",
        "article.notice",
        "li.search-result",
        "table.noticeTable tbody tr",
    ],
    anchor_hint="/procurement",
    currency="EUR",
    filter_to_jordan=True,
    notes="ebrd.com plus ECEPP; ECEPP carries the consultancy assignments",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
