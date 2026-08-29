"""KfW tenders -- published by Germany Trade & Invest, not by KfW.

KfW does NOT publish tender notices on its own website; GTAI is entrusted with
that. Pointing this module at kfw.de means the portal reports "unavailable"
forever while looking like a transport problem.
"""

from __future__ import annotations

from .base import HtmlPortal


class GtaiPortal(HtmlPortal):
    name = "gtai"
    label = "GTAI (KfW notices)"
    url = "https://www.gtai.de/en/trade/tenders"
    anchor_pattern = r"/en/trade/[\w\-/]+"
    selectors = None
