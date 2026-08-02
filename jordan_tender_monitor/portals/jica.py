"""
JICA -- Japan International Cooperation Agency. Tier 3.

Procurement is published per country office rather than centrally, so the
Jordan office page is the source. Some JICA calls are restricted to Japanese
firms; those are flagged by the eligibility detector (Q9).

VERIFICATION STATUS: never run against the live site; selectors unverified.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec

KEY = "jica"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        "https://www.jica.go.jp/jordan/english/office/others/procurement.html",
    ],
    # SELECTOR HINTS ONLY -- written without access to the live pages, which
    # were blocked from the build environment. If a hint is wrong the quality
    # gate rejects it and a class-independent layer takes over. Confirm with:
    #     python run.py --capture jica
    selectors=[
        "div.js-accordion-content li",
        "ul.list-normal li",
        "table tbody tr",
        "div.section li",
    ],
    anchor_hint="procurement",
    currency="JPY",
    filter_to_jordan=False,
    notes="Jordan country-office page; already Jordan-specific",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
