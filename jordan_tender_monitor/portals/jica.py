"""
JICA -- Japan International Cooperation Agency. Tier 3.

Procurement is published per country office rather than centrally, so the
Jordan office page is the source. Some JICA calls are restricted to Japanese
firms; those are flagged by the eligibility detector (Q9).

THE OLD URL RETURNED HTTP 404 ON EVERY LIVE RUN. JICA restructured its site:
country pages moved from

    /<country>/english/office/others/procurement.html
to
    /english/overseas/<country>/others/procurement.html

confirmed by the live Indonesia page at
/english/overseas/indonesia/others/procurement.html and the live Jordan office
at /english/overseas/jordan/office/index.html.

Both spellings are listed. The old scheme still answers for some countries
(cotedivoire, bangladesh), so JICA is evidently mid-migration, and harvest()
tolerates one source URL failing as long as another works -- which is exactly
the situation a half-finished migration creates.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec

KEY = "jica"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        # The restructured scheme first -- this is the one the live site uses.
        "https://www.jica.go.jp/english/overseas/jordan/others/procurement.html",
        # The pre-migration URL, kept because JICA still answers it for several
        # country offices and it costs one request to find out.
        "https://www.jica.go.jp/jordan/english/office/others/procurement.html",
    ],
    # SELECTOR HINTS ONLY -- written without access to the live pages, which
    # were blocked from the build environment. If a hint is wrong the quality
    # gate rejects it and a class-independent layer takes over. Confirm with:
    #     python run.py --capture jica
    selectors=[
        "div.js-accordion-content li",
        "ul.list-normal li",
        "table tbody tr",
        "div.section li",
    ],
    anchor_hint="procurement",
    currency="JPY",
    filter_to_jordan=False,
    notes="Jordan country-office page; already Jordan-specific",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
