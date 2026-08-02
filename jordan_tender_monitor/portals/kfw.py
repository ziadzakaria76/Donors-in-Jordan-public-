"""
KfW -- via Germany Trade & Invest. Tier 2.

KfW does NOT publish tender notices on kfw.de. Germany Trade & Invest is
entrusted with publishing them, so the source is gtai.de. Pointing a scraper at
kfw.de means this portal reports "unavailable" forever while looking like an
honest failure -- which is worse than not having it, because it is invisible.

VERIFICATION STATUS: never run against the live site; selectors unverified.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec

KEY = "kfw"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        "https://www.gtai.de/en/trade/tenders",
    ],
    # SELECTOR HINTS ONLY -- written without access to the live pages, which
    # were blocked from the build environment. If a hint is wrong the quality
    # gate rejects it and a class-independent layer takes over. Confirm with:
    #     python run.py --capture kfw
    selectors=[
        "div.gtai-teaser",
        "article.teaser",
        "li.search-result",
        "table tbody tr",
    ],
    anchor_hint="/tenders/",
    currency="EUR",
    filter_to_jordan=True,
    notes="KfW notices are published by GTAI, not on kfw.de",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
