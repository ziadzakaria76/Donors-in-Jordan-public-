"""
ADFD -- Abu Dhabi Fund for Development. Tier 3 -- announcements only.

ADFD has NO procurement database. It publishes project news, and tenders for
ADFD-financed projects are issued by the beneficiary government rather than by
ADFD itself. This portal is therefore expected to be quiet, and a quiet run
here is normal rather than a failure -- the report labels it as
announcement-only so the two cannot be confused.

VERIFICATION STATUS: never run against the live site; selectors unverified.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec

KEY = "adfd"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        "https://www.adfd.ae/english/MediaCenter/News/Pages/default.aspx",
    ],
    # SELECTOR HINTS ONLY -- written without access to the live pages, which
    # were blocked from the build environment. If a hint is wrong the quality
    # gate rejects it and a class-independent layer takes over. Confirm with:
    #     python run.py --capture adfd
    selectors=[
        "div.news-item",
        "li.dfwp-item",
        "article",
        "table tbody tr",
    ],
    anchor_hint="/News/",
    currency="AED",
    filter_to_jordan=True,
    notes="news announcements only; no procurement database exists",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
