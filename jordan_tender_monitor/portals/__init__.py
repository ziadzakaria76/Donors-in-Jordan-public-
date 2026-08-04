"""
Portal registry.

Every module here exposes exactly one required function:

    fetch_tenders() -> list[dict]

HTML portals additionally expose capture() and a SPEC, so `--capture PORTAL`
works for all of them -- including the ones with custom fetch logic, which are
exactly the ones most easily left out of a diagnostic by accident.
"""

from __future__ import annotations

from types import ModuleType

from .. import config
from . import (adfd, ebrd, eib, fcdo, giz, isdb, jica, kfw, samgov, sfd, ted,
               ungm, worldbank)

MODULES: dict[str, ModuleType] = {
    "worldbank": worldbank,
    "ted": ted,
    "samgov": samgov,
    "fcdo": fcdo,
    "ungm": ungm,
    "ebrd": ebrd,
    "eib": eib,
    "giz": giz,
    "kfw": kfw,
    "isdb": isdb,
    "sfd": sfd,
    "adfd": adfd,
    "jica": jica,
}


def enabled() -> dict[str, ModuleType]:
    """The portals switched on in config, in registry order."""
    return {k: m for k, m in MODULES.items() if config.ENABLED_PORTALS.get(k, False)}


def html_portals() -> dict[str, ModuleType]:
    """Portals whose pages can be captured for selector verification."""
    return {k: m for k, m in MODULES.items() if hasattr(m, "capture")}


def api_portals() -> dict[str, ModuleType]:
    """Portals whose raw JSON can be captured for field verification.

    The API portals were outside --capture entirely, which is how worldbank.py
    kept reading its link from four field names the API does not use: there was
    no command that would have shown the real ones.
    """
    return {k: m for k, m in MODULES.items() if hasattr(m, "capture_api")}


def source_urls(key: str) -> list[str]:
    """The URLs a portal polls, for the failure table in the report."""
    module = MODULES.get(key)
    if module is None:
        return []
    spec = getattr(module, "SPEC", None)
    if spec is not None:
        return list(spec.urls)
    for attr in ("API", "LISTING", "SEARCH"):
        value = getattr(module, attr, None)
        if value:
            return [value]
    return []


def name(key: str) -> str:
    return config.PORTAL_NAMES.get(key, key)


def tier(key: str) -> int:
    return config.PORTAL_TIERS.get(key, 2)
