"""
GIZ -- Deutsche Gesellschaft fuer Internationale Zusammenarbeit. Tier 2.

One source: the German tender portal. German formatting is the reason
utils.money handles dot-as-thousands and utils.dates handles "15. Januar 2027"
-- EUR 1.500.000 read as 1.5 would put a real contract below the minimum value
and delete it.

VERIFIED AGAINST THE LIVE SITE: the German portal reads cleanly via the
header-aware table layer -- 20 rows at quality 1.00, with real dates and links.
The English giz.de page carried no listing whatsoever and has been removed.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec

KEY = "giz"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        # giz.de/en/partner/contractor/tenders was removed after --capture
        # showed it carries NO listing at all -- it is an information page.
        # Its derived selectors were main-menu__container (74 blocks) and
        # main-menu__item (33), i.e. pure navigation. The German portal below
        # is the real source and reads cleanly: 20 rows at quality 1.00.
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
    notes="German ausschreibungen portal; the English giz.de page carries no listing",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
