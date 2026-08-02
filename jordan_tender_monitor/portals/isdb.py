"""
Islamic Development Bank procurement notices.

Jordan is an IsDB member country with an active portfolio, so this portal is
worth monitoring despite inconsistent markup. isdb.org is Drupal-based, which
means the embedded-JSON extraction layer often recovers rows even when the
rendered classes change.
"""

from __future__ import annotations

from .harvester import Source, harvest

PORTAL_KEY = "isdb"
LABEL = "IsDB"
MANUAL_URL = "https://www.isdb.org/procurement"

# URLs verified August 2026. IsDB tenders live under /project-procurement/,
# not the /procurement paths from the original brief.
SOURCES = [
    Source("https://www.isdb.org/project-procurement/tenders"),
    Source("https://www.isdb.org/project-procurement/taxonomy/term/207"),  # GPN category
    Source("https://www.isdb.org/project-procurement/documents"),
    Source("https://www.isdb.org/procurement"),  # legacy, in case of redirect
]

SELECTORS = [
    "div.procurement-item", "div.views-row", "table tbody tr",
    "article.node", "li.item", "div.card",
    "div[class*='procurement']", "div[class*='views-row']",
]

# Real notice permalinks:
#   /project-procurement/tenders/2026/gpn/islamic-finance-legal-framework-...
HREF_PATTERN = r"(/project-procurement/tenders/|procurement|tender|notice|node/\d+)"


def fetch_tenders() -> list[dict]:
    return harvest(
        portal_key=PORTAL_KEY,
        label=LABEL,
        sources=SOURCES,
        selectors=SELECTORS,
        href_pattern=HREF_PATTERN,
        notice_type="IsDB procurement notice",
        manual_url=MANUAL_URL,
    )
