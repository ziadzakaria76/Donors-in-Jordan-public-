"""UNDP procurement notices.

Detail pages follow view_notice.cfm?notice_id=NNNNN, which is a clean anchor-URL
pattern for the cascade's last layer.

Behind this portal, UNDP's Quantum supplier portal also serves UNFPA, UN Women,
UNCDF and UNV, so those agencies' notices surface here too.

SELECTORS BELOW ARE UNVERIFIED GUESSES -- this environment could not reach the
site. The class-independent layers (embedded JSON, header tables, structural
inference, anchor pattern) are what this portal actually relies on; confirm or
replace the selectors with `--capture undp`.
"""

from __future__ import annotations

from .base import HtmlPortal

BASE = "https://procurement-notices.undp.org"


class UndpPortal(HtmlPortal):
    name = "undp"
    label = "UNDP"
    url = BASE + "/"
    anchor_pattern = r"view_notice\.cfm\?notice_id=\d+"
    selectors = None          # guesses removed rather than shipped unverified
