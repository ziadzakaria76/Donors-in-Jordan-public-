"""Portal registry.

Portals are constructed through this registry and collected through
BasePortal.collect(), which applies the shared country gate. A portal module
cannot opt out of that check by omission -- it never performs the check itself.
"""

from __future__ import annotations

from typing import Type

from .base import BasePortal, PortalOutcome
from . import giz, gtai, isdb, samgov, srtf, ted, uk_fts, ungm, undp, worldbank

# EBRD and EIB are deliberately absent.
#   EBRD: Syria is eligible to join but is not a member and is not among the
#         Bank's countries of operations, so it publishes no Syria procurement.
#   EIB:  Syria was removed from the EIB external-mandate eligible-country list
#         by Delegated Act in April 2012 and has not been restored.
# Both are core to a Jordan build; neither belongs here. Recorded so nobody
# re-adds them assuming they were an oversight. Worth revisiting rather than
# treating as permanent: Syrian EBRD membership is under active advocacy, and a
# proposed EU-UN guarantee window involving EIB or EBRD has first transactions
# expected in 2027.
#
# Commercial aggregators (syriatenders.com, tendersontime.com,
# rebuilding-syria.com) are also absent by design: they resell notices, are
# often paywalled and stale, sometimes restrict scraping in their terms, and
# their provenance is unverifiable. UN Development Business and dgMarket are
# legitimate donor publication channels rather than resellers, but UNDB is
# subscription-based -- check access before depending on either.

REGISTRY: dict[str, Type[BasePortal]] = {
    worldbank.WorldBankPortal.name: worldbank.WorldBankPortal,
    ted.TedPortal.name: ted.TedPortal,
    samgov.SamGovPortal.name: samgov.SamGovPortal,
    uk_fts.UkFindATenderPortal.name: uk_fts.UkFindATenderPortal,
    ungm.UngmPortal.name: ungm.UngmPortal,
    undp.UndpPortal.name: undp.UndpPortal,
    srtf.SrtfPortal.name: srtf.SrtfPortal,
    giz.GizPortal.name: giz.GizPortal,
    isdb.IsdbPortal.name: isdb.IsdbPortal,
    gtai.GtaiPortal.name: gtai.GtaiPortal,
}

HTML_PORTALS = [name for name, cls in REGISTRY.items() if cls.is_html]

__all__ = ["BasePortal", "PortalOutcome", "REGISTRY", "HTML_PORTALS"]
