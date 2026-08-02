"""
EBRD procurement notices (HTML).

EBRD publishes notices on ebrd.com and runs its full tendering system on ECEPP.
Both are tried. Jordan is a relatively recent EBRD country of operation, so
volumes are usually low.
"""

from __future__ import annotations

from .harvester import Source, harvest

PORTAL_KEY = "ebrd"
LABEL = "EBRD"
MANUAL_URL = "https://www.ebrd.com/work-with-us/procurement.html"

# URLs verified August 2026. EBRD moved project procurement under
# /home/work-with-us/project-procurement/ and runs live tendering on ECEPP,
# whose search results page is noticeSearchResults.html (not the
# searchContractNotice.html this module previously targeted).
SOURCES = [
    Source("https://www.ebrd.com/home/work-with-us/project-procurement/procurement-notices.html"),
    Source("https://ecepp.ebrd.com/delta/noticeSearchResults.html", js=True),
    Source("https://www.ebrd.com/home/work-with-us/corporate-procurement-consultancy-services.html"),
    # Legacy paths, kept as fallbacks in case of redirects
    Source("https://www.ebrd.com/work-with-us/procurement/notices.html"),
]

SELECTORS = [
    "div.procurement-notice", "li.search-result", "article.notice",
    "table.notices tbody tr", "div.result-item", "div.views-row",
    "div[class*='notice']", "li[class*='result']",
]

# ECEPP notice permalinks look like:
#   https://ecepp.ebrd.com/delta/viewNotice.html?displayNoticeId=39536445
HREF_PATTERN = r"(viewNotice\.html|displayNoticeId=|procurement-notices|(procurement|notice|tender|contract).*(\.html|/\d+))"


def fetch_tenders() -> list[dict]:
    return harvest(
        portal_key=PORTAL_KEY,
        label=LABEL,
        sources=SOURCES,
        selectors=SELECTORS,
        href_pattern=HREF_PATTERN,
        notice_type="EBRD procurement notice",
        manual_url=MANUAL_URL,
    )
