"""
Saudi Fund for Development -- announcement scraping only (LIMITED RELIABILITY).

SFD has no structured procurement database. It publishes tender and project
announcements, mostly in Arabic, across its news and tenders pages. Both the
Arabic and English trees are scraped; Arabic text is preserved as published and
flagged downstream for manual review (Q8 = include both, flag Arabic).
"""

from __future__ import annotations

from .harvester import Source, harvest

PORTAL_KEY = "sfd"
LABEL = "Saudi Fund for Development"
MANUAL_URL = "https://www.sfd.gov.sa"

# URLs verified August 2026. The live listing is /en/tenders-view (the plain
# /en/tenders path used previously is not the tender board).
SOURCES = [
    Source("https://www.sfd.gov.sa/en/tenders-view"),
    Source("https://www.sfd.gov.sa/ar/tenders-view"),
    Source("https://www.sfd.gov.sa/en/internal-tenders-view"),
    Source("https://www.sfd.gov.sa/en/news"),
    Source("https://www.sfd.gov.sa/ar/news"),
]

SELECTORS = [
    "div.tender-card", "div.news-card", "div.card", "article",
    "li.list-item", "div.views-row", "table tbody tr",
    "div[class*='tender']", "div[class*='news']",
]

HREF_PATTERN = r"(tender|news|منافس|مناقص|أخبار)"


def fetch_tenders() -> list[dict]:
    return harvest(
        portal_key=PORTAL_KEY,
        label=LABEL,
        sources=SOURCES,
        selectors=SELECTORS,
        href_pattern=HREF_PATTERN,
        notice_type="SFD announcement",
        manual_url=MANUAL_URL,
    )
