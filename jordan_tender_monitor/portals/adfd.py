"""
Abu Dhabi Fund for Development -- press-release scraping only (LIMITED RELIABILITY).

ADFD publishes no procurement database at all. What exists is news announcing
financing agreements, which is useful as an early signal that procurement will
follow. Items are captured as leads, not live tenders, and labelled as such.
"""

from __future__ import annotations

from .harvester import Source, harvest

PORTAL_KEY = "adfd"
LABEL = "Abu Dhabi Fund for Development"
MANUAL_URL = "https://www.adfd.ae"

SOURCES = [
    Source("https://www.adfd.ae/english/MediaCenter/Pages/News.aspx"),
    Source("https://www.adfd.ae/english/Pages/default.aspx"),
    Source("https://www.adfd.ae/arabic/MediaCenter/Pages/News.aspx"),
]

SELECTORS = [
    "div.news-item", "div.card", "article", "li.item",
    "div.ms-rtestate-field p", "table tbody tr",
    "div[class*='news']", "div[class*='media']",
]

HREF_PATTERN = r"(news|media|press|article|Pages/)"


def fetch_tenders() -> list[dict]:
    return harvest(
        portal_key=PORTAL_KEY,
        label=LABEL,
        sources=SOURCES,
        selectors=SELECTORS,
        href_pattern=HREF_PATTERN,
        notice_type="ADFD announcement (lead, not a live tender)",
        manual_url=MANUAL_URL,
        # Press releases have no deadline to recover; skip the extra requests.
        enrich=False,
    )
