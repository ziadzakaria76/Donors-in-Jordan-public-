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

THE REBUILT SITE RENDERS ITS CONTENT IN JAVASCRIPT. --capture on the correct
URL returned 28 KB that is nothing but the mega-menu -- "Who We Are", "What We
Do", "Our Impact" -- and every class-independent layer found zero rows. That
is the UNGM signature: the page loads, and the listing is not in it.

So this portal renders too. Playwright stays optional; without it ADFD reports
the install commands as its reason, exactly as UNGM does, and the other twelve
portals are unaffected.

A quiet run remains normal for this portal. What is no longer acceptable is a
quiet run that was really a 404, or a shell, in disguise.
"""

from __future__ import annotations

from . import base, browser, harvester
from .harvester import HtmlSpec

KEY = "adfd"

def _fetch_rendered(url: str) -> str:
    """Render in a headless browser -- the markup alone carries no listing."""
    if not browser.available():
        raise base.PortalError(
            f"ADFD renders its listing in JavaScript: {browser.INSTALL_HINT}", url)
    return browser.render(url, wait_for=ROW_HINT)


# A hint only, as on UNGM: if it never appears the DOM is still read after the
# settle delay, so a renamed class degrades to a weak result the cascade can
# diagnose rather than a hard failure.
ROW_HINT = "div.tender-item, div.card, table tbody tr, article"

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
    fetcher=_fetch_rendered,
    currency="AED",
    filter_to_jordan=True,
    notes="procurement tenders page plus news announcements",
)


def fetch_tenders() -> list[dict]:
    return harvester.harvest(SPEC)


def capture():
    return harvester.capture(SPEC)
