"""
ADFD -- Abu Dhabi Fund for Development. Tier 3.

THE MODULE PREVIOUSLY ASSERTED THAT ADFD HAS NO PROCUREMENT DATABASE. That was
wrong, and it was wrong in the way that costs most: a confident comment
explaining away an empty result. It pointed at the news page instead, which
reported "layout change - no layer found a listing" on every live run -- a
failure that looked like a scraper problem and was really a wrong URL.

ADFD publishes procurement tenders at

    /english/Eservices/Tender/Pages/Procurementtenders.aspx

That page is now the first source. The news page is kept second, because
tenders for ADFD-financed projects are genuinely often issued by the
beneficiary government and announced as news rather than listed here -- so it
is a real secondary source, not a fallback for a broken primary.

A quiet run remains normal for this portal. What is no longer acceptable is a
quiet run that was really a 404 in disguise.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec

KEY = "adfd"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        "https://www.adfd.ae/english/Eservices/Tender/Pages/Procurementtenders.aspx",
        "https://www.adfd.ae/english/MediaCenter/News/Pages/default.aspx",
    ],
    # SELECTOR HINTS ONLY -- written without access to the live pages, which
    # were blocked from the build environment. If a hint is wrong the quality
    # gate rejects it and a class-independent layer takes over. Confirm with:
    #     python run.py --capture adfd
    #
    # This is a SharePoint site (.aspx, dfwp = Data Form Web Part), so the
    # generated markup is the usual web-part soup and the class-independent
    # layers are likely to do the real work here.
    selectors=[
        "div.tender-item",
        "li.dfwp-item",
        "div.news-item",
        "table.ms-listviewtable tbody tr",
    ],
    # The tenders page is the primary source now, so the anchor hint must not
    # be pinned to /News/ -- that was silently excluding every tender link from
    # the anchor layer.
    anchor_hint=None,
    currency="AED",
    filter_to_jordan=True,
    notes="procurement tenders page plus news announcements",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
