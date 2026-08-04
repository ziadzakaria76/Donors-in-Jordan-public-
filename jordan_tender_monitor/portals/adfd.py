"""
ADFD -- Abu Dhabi Fund for Development. Tier 3.

THE MODULE PREVIOUSLY ASSERTED THAT ADFD HAS NO PROCUREMENT DATABASE. That was
wrong, and it was wrong in the way that costs most: a confident comment
explaining away an empty result. It pointed at the news page instead, which
reported "layout change - no layer found a listing" on every live run -- a
failure that looked like a scraper problem and was really a wrong URL.

ADFD does publish tenders, at

    /en/what-we-do/tenders

The .aspx path that search engines still index is legacy. --capture showed it
answers 200 with nothing but chrome: the repeated blocks were div.row,
div.container and div.footer-links, and the row anatomy was the "Who we are"
menu. ADFD has rebuilt on a /en/<section>/<page> scheme, so it has been
dropped rather than kept -- a URL that reliably carries no listing is a
permanent failure line, not a fallback.

The news page is kept second, because tenders for ADFD-financed projects are
genuinely often issued by the beneficiary government and announced as news
rather than listed here -- a real secondary source, not a spare tyre.

ADFD PUBLISHES NO MACHINE-READABLE TENDER LISTING. Four URLs and two fetch
strategies were tried, and the conclusion is negative rather than pending:

  * /english/Eservices/Tender/Pages/Procurementtenders.aspx -- legacy. 200,
    and nothing but chrome.
  * /english/MediaCenter/News/Pages/default.aspx -- legacy, same.
  * /en/what-we-do/tenders -- the current page. 28 KB, all mega-menu, zero
    rows from every layer.
  * /en/media-centre/news -- same.

A headless browser was then tried, on the UNGM analogy, AND IT DID NOT HELP.
The render plainly worked -- the page grew to 34 KB and section.aos-animate
appeared, a class that only exists once Animate-On-Scroll initialises in a
real browser -- and every layer still found zero rows. So the listing is not
being hidden by JavaScript; it is not there. Playwright was removed again
rather than left in place looking useful: 400 MB of dependency that provably
changes nothing is worse than none.

This portal therefore reports "no listing published", like JICA. What cannot
be distinguished from outside is "no open tenders today" from "the listing
needs an interaction to appear"; the reason text says so rather than implying
certainty.

That is consistent with what ADFD is: it finances projects, and tenders for
ADFD-financed work are issued by the beneficiary government. The original
module said something close to this -- and was still wrong to say it without
checking, which is how it ended up pointing at a news page for years.
"""

from __future__ import annotations

from . import base, harvester
from .harvester import HtmlSpec

KEY = "adfd"

SPEC = HtmlSpec(
    key=KEY,
    urls=[
        "https://www.adfd.ae/en/what-we-do/tenders",
        "https://www.adfd.ae/en/media-centre/news",
    ],
    # SELECTOR HINTS ONLY -- written without access to the live pages, which
    # were blocked from the build environment. If a hint is wrong the quality
    # gate rejects it and a class-independent layer takes over. Confirm with:
    #     python run.py --capture adfd
    #
    # NOT SharePoint. The earlier hints assumed .aspx meant SharePoint web
    # parts; the capture showed a Bootstrap rebuild (div.row, div.container,
    # div.col-lg-6), so dfwp-item and ms-listviewtable could never have
    # matched. These are generic hints for that style, and the
    # class-independent layers are expected to do the real work.
    selectors=[
        "div.tender-item",
        "div.card",
        "div.news-item",
        "table tbody tr",
    ],
    # The tenders page is the primary source now, so the anchor hint must not
    # be pinned to /News/ -- that was silently excluding every tender link from
    # the anchor layer.
    anchor_hint=None,
    currency="AED",
    filter_to_jordan=True,
    notes="procurement tenders page plus news announcements",
)


def fetch_tenders() -> list[dict]:
    try:
        return harvester.harvest(SPEC)
    except base.PortalError as exc:
        # See the docstring: four URLs, plain and rendered, all carry chrome
        # and no listing. That is a fact about ADFD, not a broken scraper, and
        # a permanent red line in the status table teaches the reader to stop
        # looking at it. The underlying reason is kept so a real change --
        # a bot wall, a transport error -- is still visible.
        raise base.PortalError(
            "no listing published - ADFD's tenders page carries no listing "
            "(rendered or not); its financed tenders are issued by the "
            f"beneficiary government. Detail: {exc.reason}",
            exc.url) from exc


def capture():
    return harvester.capture(SPEC)
