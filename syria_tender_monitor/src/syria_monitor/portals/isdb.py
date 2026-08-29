"""Islamic Development Bank project procurement.

A genuine active source here, unlike in any pre-2025 build: this country's IsDB
membership was restored on 16 March 2025 by the Board of Executive Directors,
following reinstatement to the OIC on 8 March 2025 after a 13-year suspension.

Both dates are from the tier-3 (unverified) set -- re-check them; this
environment could not reach isdb.org.
"""

from __future__ import annotations

from .base import HtmlPortal


class IsdbPortal(HtmlPortal):
    name = "isdb"
    label = "IsDB"
    url = "https://www.isdb.org/project-procurement/tenders"
    anchor_pattern = r"/project-procurement/[\w\-/]+"
    selectors = None
