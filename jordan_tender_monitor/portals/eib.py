"""
European Investment Bank procurement notices (HTML).

Covers EIB corporate procurement plus notices tied to the projects it finances.
Only Jordan-related items are kept.
"""

from __future__ import annotations

from .harvester import Source, harvest

PORTAL_KEY = "eib"
LABEL = "EIB"
MANUAL_URL = "https://www.eib.org/en/projects/procurement/index.htm"

# URLs verified August 2026. EIB procurement lives under /en/about/procurement/
# (not /en/projects/procurement/, which this module previously used). The
# "all" index is the actual listing of open calls.
SOURCES = [
    Source("https://www.eib.org/en/about/procurement/all/index.htm"),
    Source("https://www.eib.org/en/about/procurement/index"),
    Source("https://www.eib.org/en/about/procurement/project-procurement"),
    Source("https://www.eib.org/en/about/procurement/technical-assistance.htm"),
    Source("https://www.eib.org/en/projects/all/index.htm", params={"q": "Jordan"}),
]

SELECTORS = [
    "div.eib-listing__item", "li.listing__item", "article.teaser",
    "div.search-result", "table tbody tr", "div.views-row",
    "div[class*='listing']", "article[class*='teaser']",
]

# Real call permalinks:
#   /en/about/procurement/calls/all/cft-1744
#   /en/about/procurement/calls-technical-assistance/all/aa-011624003
HREF_PATTERN = r"/(projects|about)/(procurement|pipelines|all)/|/procurement/calls"


def fetch_tenders() -> list[dict]:
    return harvest(
        portal_key=PORTAL_KEY,
        label=LABEL,
        sources=SOURCES,
        selectors=SELECTORS,
        href_pattern=HREF_PATTERN,
        notice_type="EIB procurement notice",
        manual_url=MANUAL_URL,
    )
