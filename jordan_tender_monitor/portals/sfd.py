"""
Saudi Fund for Development. Tier 3 -- announcements only.

Publishes in Arabic and English, and many calls are restricted to Saudi firms
or Saudi-led joint ventures. Those restrictions are detected and flagged rather
than excluded, because a JV route may still be open (Q9).

Arabic content is kept in the original and flagged for manual review (Q8).

VERIFICATION STATUS: never run against the live site; selectors unverified.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec

KEY = "sfd"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        "https://www.sfd.gov.sa/en/tenders-view",
        "https://www.sfd.gov.sa/ar/tenders-view",
    ],
    # SELECTOR HINTS ONLY -- written without access to the live pages, which
    # were blocked from the build environment. If a hint is wrong the quality
    # gate rejects it and a class-independent layer takes over. Confirm with:
    #     python run.py --capture sfd
    selectors=[
        "div.tender-item",
        "div.card",
        "table tbody tr",
        "li.tender",
    ],
    anchor_hint="tender",
    currency="SAR",
    filter_to_jordan=True,
    notes="Arabic and English; Saudi-firm restrictions flagged",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
