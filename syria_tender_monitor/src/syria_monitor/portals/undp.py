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
    # READ OFF THE LIVE PAGE, not guessed -- the previous value was None with
    # the note "guesses removed rather than shipped unverified", and this is
    # what the capture of 2026-08-30 (Actions run 33287873872) reported:
    #
    #   a.vacanciesTableLink x572, a.vacanciesTable__row x572
    #
    # The run was reading SIX of those 572. Every row carries its own country
    # and region in its class list --
    #
    #   34->34 q=0.44 a.country_4.region_RAS.vacanciesTableLink.vacanciesTable__row
    #   21->21 q=0.42 a.country_5.region_RAS.vacanciesTableLink.vacanciesTable__row
    #   49->49 q=0.40 a.country_5.region_RER.vacanciesTableLink.vacanciesTable__row
    #
    # -- so grouping by class signature shatters one listing into dozens of
    # per-country fragments, the largest 49, none of them reaching the 0.45
    # threshold. A six-row structural group won at 0.55 instead.
    #
    # That is the same shape of failure as UNGM's, arrived at from the opposite
    # direction: there one group beat the right one, here the right group never
    # formed. Both are answered by naming the row.
    #
    # The title is deliberately NOT pinned. The page holds
    # div.vacanciesTable__cell x3438 -- six per row -- and which one is the
    # title is not established by anything in that capture. Guessing it is what
    # the note this replaces was warning about; the next capture prints the
    # cells and settles it.
    selectors = {"row": "a.vacanciesTableLink"}
