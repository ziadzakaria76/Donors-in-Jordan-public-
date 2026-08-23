"""Syria Recovery Trust Fund.

A country-specific donor vehicle with its own procurement and no analogue in a
Jordan build. It also publishes ICB/LIB/NCB notices to UN Development Business
and dgMarket, which is a useful cross-check on whether this scraper is complete
-- if SRTF notices appear there and not here, the extraction has drifted.

SELECTORS ARE UNVERIFIED -- see undp.py.
"""

from __future__ import annotations

from .base import HtmlPortal


class SrtfPortal(HtmlPortal):
    name = "srtf"
    label = "Syria Recovery Trust Fund"
    url = "https://www.srtfund.org/procurements/list"
    anchor_pattern = r"/procurements?/[\w\-/]+"
    selectors = None
