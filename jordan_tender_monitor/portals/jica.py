"""
JICA procurement notices -- LIMITED RELIABILITY for this use case.

JICA's consultant procurement is largely restricted to Japanese firms and its
English-language Jordan content is sparse. Included for completeness; expect few
or no results, and treat anything found as a lead to verify manually.
"""

from __future__ import annotations

from .harvester import Source, harvest

PORTAL_KEY = "jica"
LABEL = "JICA"
MANUAL_URL = "https://www.jica.go.jp/english/our_work/procurement/"

# URLs verified August 2026. JICA posts most procurement on its country-office
# pages, which follow /<country>/english/office/others/procurement.html, plus a
# central notices index.
SOURCES = [
    Source("https://www.jica.go.jp/english/notice/index.html"),
    Source("https://www.jica.go.jp/announce/notice/index.html"),
    Source("https://www.jica.go.jp/jordan/english/office/others/procurement.html"),
    Source("https://www.jica.go.jp/jordan/english/office/others/bidding.html"),
    Source("https://www.jica.go.jp/english/our_work/types_of_assistance/oda_loans/"
           "oda_op_info/guide/tender/index.html"),
]

SELECTORS = [
    "div.tender-list li", "ul.list-news li", "table tbody tr",
    "div.js-accordion-content li", "article", "div.section li",
    "div[class*='tender']", "ul[class*='list'] li",
]

HREF_PATTERN = r"(tender|procurement|announce|notice)"


def fetch_tenders() -> list[dict]:
    return harvest(
        portal_key=PORTAL_KEY,
        label=LABEL,
        sources=SOURCES,
        selectors=SELECTORS,
        href_pattern=HREF_PATTERN,
        notice_type="JICA notice",
        manual_url=MANUAL_URL,
        default_eligibility="Often restricted to Japanese firms - verify eligibility",
    )
