"""
KfW Development Bank procurement notices.

Important: KfW does not publish its international tender notices on its own
website. Germany Trade & Invest (GTAI) is formally entrusted with publishing
planned KfW-financed projects and their International Competitive Biddings, so
gtai.de is the primary source here; kfw-entwicklungsbank.de carries procurement
*regulations* rather than notices.

GTAI aggregates tenders from several financiers (KfW, GIZ, EU, World Bank, UN,
AfDB, ADB). Anything Jordan-related found there is captured; where the same
tender also appears on its originating portal, the deduplicator merges the two
and annotates "Also found on".

URLs verified August 2026.
"""

from __future__ import annotations

from .harvester import Source, harvest

PORTAL_KEY = "kfw"
LABEL = "KfW"
MANUAL_URL = "https://www.gtai.de/en/trade/tenders"

SOURCES = [
    # GTAI -- where KfW tenders are actually published
    Source("https://www.gtai.de/en/trade/tenders"),
    Source("https://www.gtai.de/de/trade/ausschreibungen-projekte"),
    # Agentur für Wirtschaft & Entwicklung aggregates KfW and GIZ invitations
    Source("https://wirtschaft-entwicklung.de/en/international-tenders/german-organisations"),
    # KfW's own pages, for completeness
    Source("https://www.kfw-entwicklungsbank.de/Service/Procurement-Regulations/"),
    Source("https://www.kfw-entwicklungsbank.de/International-financing/KfW-Development-Bank/"),
]

SELECTORS = [
    "div.tender", "li.teaser", "div.c-teaser", "table tbody tr",
    "article", "div.contentbox", "div.list-item",
    "div[class*='tender']", "div[class*='teaser']", "div[class*='result']",
]

HREF_PATTERN = r"(ausschreibung|tender|procurement|vergabe|/trade/)"


def fetch_tenders() -> list[dict]:
    return harvest(
        portal_key=PORTAL_KEY,
        label=LABEL,
        sources=SOURCES,
        selectors=SELECTORS,
        href_pattern=HREF_PATTERN,
        notice_type="KfW / GTAI tender",
        manual_url=MANUAL_URL,
    )
