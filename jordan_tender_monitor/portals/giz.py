"""
GIZ -- Deutsche Gesellschaft fuer Internationale Zusammenarbeit. Tier 2.

Two sources: the English contractor page and the German tender portal, which
carries considerably more. German formatting is the reason utils.money handles
dot-as-thousands and utils.dates handles "15. Januar 2027" -- EUR 1.500.000
read as 1.5 would put a real contract below the minimum value and delete it.

VERIFICATION STATUS: never run against the live site; selectors unverified.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec

KEY = "giz"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        "https://www.giz.de/en/partner/contractor/tenders",
        "https://ausschreibungen.giz.de/Satellite/company/welcome.do",
    ],
    # SELECTOR HINTS ONLY -- written without access to the live pages, which
    # were blocked from the build environment. If a hint is wrong the quality
    # gate rejects it and a class-independent layer takes over. Confirm with:
    #     python run.py --capture giz
    selectors=[
        "div.tender-item",
        "tr.tableRow",
        "table.publicationTable tbody tr",
        "li.result",
    ],
    anchor_hint="/Satellite/notice",
    currency="EUR",
    filter_to_jordan=True,
    notes="English page plus the German ausschreibungen portal",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
