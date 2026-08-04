"""
JICA -- Japan International Cooperation Agency. Tier 3.

Procurement is published per country office rather than centrally, so the
Jordan office page is the source. Some JICA calls are restricted to Japanese
firms; those are flagged by the eligibility detector (Q9).

JICA'S JORDAN OFFICE PUBLISHES NO PROCUREMENT PAGE. This was chased down
properly rather than guessed at:

  * The original URL 404s. JICA did restructure, moving country pages from
    /<country>/english/office/others/ to /english/overseas/<country>/others/.
  * Bangladesh and Indonesia answer on BOTH schemes, so the new spelling is
    right and the old one still works where a page exists.
  * Jordan 404s on BOTH. Repeated searches surface procurement pages for
    Bangladesh, Indonesia, Cote d'Ivoire and the Balkan office, and never one
    for Jordan.

So this is not a broken scraper and no URL will fix it. The portal reports
"no listing published", which the run classifies apart from a failure: a
source with nothing to read must not put a permanent red line in every report,
because that is how a reader learns to ignore the status table, and the status
table is the alarm.

THE OFFICE INDEX WAS TRIED AS A SOURCE AND REMOVED. It exists and returns 200,
which made it look like the sensible fallback, and it put two phantom tenders
straight into the report:

    [22.5] Message from the Chief Representative   JICA | Unclassified
    [22.5] Related Information                     JICA | Unclassified

Those are the page's own section headings. A clean, honest 404 became a
listing of navigation dressed as opportunities -- strictly worse than the
failure it replaced, and the exact mistake this portal already made once by
asserting its way around an empty result. An index page is not a listing.
"""

from __future__ import annotations

from . import base, harvester
from .harvester import HtmlSpec

KEY = "jica"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        # Both procurement spellings, and nothing else. They 404 today; if JICA
        # Jordan ever publishes a procurement page it will be at one of these,
        # and this portal starts working with no code change. Adding a page
        # that merely EXISTS, to avoid an empty result, is what produced two
        # phantom tenders -- see the docstring.
        "https://www.jica.go.jp/english/overseas/jordan/others/procurement.html",
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
    try:
        return harvester.harvest(SPEC)
    except base.PortalError as exc:
        # Every source failing here means the same thing every time, and it is
        # not a scraper fault -- see the module docstring. The original reason
        # is kept so a genuine change (a bot wall, a transport error) is still
        # visible and still distinguishable from "there is nothing here".
        raise base.PortalError(
            "no listing published - JICA's Jordan office has no procurement "
            "page; its notices, when there are any, appear on the office index "
            f"or via the Ministry of Planning. Detail: {exc.reason}",
            exc.url) from exc


def capture():
    return harvester.capture(SPEC)
