"""
IsDB -- Islamic Development Bank. Tier 2.

Jordan is a member country, so IsDB-financed procurement appears regularly.
Note that some IsDB calls are restricted to member-country firms; those are
flagged by the eligibility detector rather than dropped (Q9).

VERIFICATION STATUS: never run against the live site; selectors unverified.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec

KEY = "isdb"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        "https://www.isdb.org/project-procurement/tenders",
    ],
    # SELECTOR HINTS ONLY -- written without access to the live pages, which
    # were blocked from the build environment. If a hint is wrong the quality
    # gate rejects it and a class-independent layer takes over. Confirm with:
    #     python run.py --capture isdb
    selectors=[
        "div.views-row",
        "div.tender-card",
        "article.node--type-tender",
        "table tbody tr",
    ],
    anchor_hint="/project-procurement/",
    currency="USD",
    filter_to_jordan=True,
    notes="member-country restrictions are flagged, not dropped",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
