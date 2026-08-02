"""
GIZ (Deutsche Gesellschaft fuer Internationale Zusammenarbeit) tender notices.

GIZ runs a large Jordan portfolio. International tenders appear on the GIZ site
and on its own e-procurement platform; both are tried. Dates here are typically
German-format (31.12.2026, "15. Januar 2027"), which base.parse_date handles.
"""

from __future__ import annotations

from .harvester import Source, harvest

PORTAL_KEY = "giz"
LABEL = "GIZ"
MANUAL_URL = "https://www.giz.de/en/mediacenter/117.html"

# URLs verified August 2026. The tenders index is /en/partner/contractor/tenders
# -- the /en/mediacenter/117.html path from the original brief is the old media
# centre and carries no tender listings. GIZ also runs country tender pages
# under /en/regions/<region>/<country>/tenders.
SOURCES = [
    Source("https://www.giz.de/en/partner/contractor/tenders"),
    Source("https://ausschreibungen.giz.de", js=True),
    Source("https://www.giz.de/en/regions/middle-east/jordan/tenders"),
    Source("https://www.giz.de/en/worldwide/jordan.html"),
]

SELECTORS = [
    "div.tender-item", "li.tender", "table.tenders tbody tr",
    "div.c-teaser", "article", "table tbody tr", "div.list-item",
    "div[class*='tender']", "div[class*='ausschreibung']",
]

# Real notice permalinks look like /en/invitation-tender-7000004018-supply-...
# and /en/procurement-goods-supply-it-equipment-software
HREF_PATTERN = r"(invitation-tender|procurement-|ausschreibung|tender|vergabe|/\d{2,6}\.html)"


def fetch_tenders() -> list[dict]:
    return harvest(
        portal_key=PORTAL_KEY,
        label=LABEL,
        sources=SOURCES,
        selectors=SELECTORS,
        href_pattern=HREF_PATTERN,
        notice_type="GIZ tender",
        manual_url=MANUAL_URL,
    )
