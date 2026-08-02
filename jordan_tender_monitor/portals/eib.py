"""
EIB -- European Investment Bank. Tier 2.

The EIB publishes its own corporate procurement and, separately, notices for
projects it finances. Jordan appears mainly under the latter.

VERIFICATION STATUS: never run against the live site; selectors unverified.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec

KEY = "eib"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        "https://www.eib.org/en/about/procurement/all/index.htm",
    ],
    # SELECTOR HINTS ONLY -- written without access to the live pages, which
    # were blocked from the build environment. If a hint is wrong the quality
    # gate rejects it and a class-independent layer takes over. Confirm with:
    #     python run.py --capture eib
    selectors=[
        "div.eib-list__item",
        "article.teaser",
        "li.list-item",
        "table tbody tr",
    ],
    anchor_hint="/about/procurement/",
    currency="EUR",
    filter_to_jordan=True,
    notes="corporate and project procurement in one listing",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
