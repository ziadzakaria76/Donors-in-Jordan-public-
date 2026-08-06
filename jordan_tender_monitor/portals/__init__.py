"""
Portal registry.

The list of portals is data -- `portals.json`, read and validated by
`portal_config.py`. This module turns each validated entry into something that
can be run, and every one of them exposes the same required function:

    fetch_tenders() -> list[dict]

HTML portals additionally expose capture() and a SPEC, so `--capture PORTAL`
works for all of them -- including the ones with custom fetch logic, which are
exactly the ones most easily left out of a diagnostic by accident.

An entry with no `module` becomes a DataPortal and goes through the generic
cascade. An entry naming a module gets that module, whose spec is still built
from the file for everything the module does not own in code. The set of
importable modules is a fixed whitelist in portal_config.CUSTOM_MODULES: this
file is written over the GitHub API by the phone app, and importing whatever a
JSON field names would turn a config write into arbitrary code execution.
"""

from __future__ import annotations

from .. import config, portal_config
from . import datadriven, fcdo, samgov, ted, ungm, worldbank

# The whitelist, resolved. portal_config.CUSTOM_MODULES holds the names; this
# holds the modules, and a test pins the two together.
_CUSTOM = {
    "worldbank": worldbank,
    "ted": ted,
    "samgov": samgov,
    "fcdo": fcdo,
    "ungm": ungm,
}


def _build() -> dict:
    """Every usable portal, in the order the file declares them."""
    built = {}
    for portal in portal_config.REGISTRY.portals:
        if portal.module:
            module = _CUSTOM.get(portal.module)
            if module is None:      # unreachable: the loader whitelists these
                continue
            built[portal.key] = module
        else:
            built[portal.key] = datadriven.build(portal.key)
    return built


MODULES: dict = _build()


def rebuild_from(path=None) -> dict:
    """Re-read the portal file and rebuild the registry, in place.

    MODULES is mutated rather than replaced because other modules hold a
    reference to it -- and because the test suite swaps its contents in and out
    to run the scraper against stand-ins.

    Note what this does NOT rebuild: the module-level endpoints in the five
    coded portals, which are bound at import. Nothing in a run re-reads the
    file, so that costs nothing today; a caller pointing this at a different
    file (the test suite) is choosing data-only portals by definition.
    """
    portal_config.reload(path)
    config.refresh_portals()
    MODULES.clear()
    MODULES.update(_build())
    return MODULES


def enabled() -> dict:
    """The portals switched on in config, in registry order."""
    return {k: m for k, m in MODULES.items() if config.ENABLED_PORTALS.get(k, False)}


def html_portals() -> dict:
    """Portals whose pages can be captured for selector verification."""
    return {k: m for k, m in MODULES.items() if hasattr(m, "capture")}


def api_portals() -> dict:
    """Portals whose raw JSON can be captured for field verification.

    The API portals were outside --capture entirely, which is how worldbank.py
    kept reading its link from four field names the API does not use: there was
    no command that would have shown the real ones.
    """
    return {k: m for k, m in MODULES.items() if hasattr(m, "capture_api")}


def source_urls(key: str) -> list[str]:
    """The URLs a portal polls, for the failure table in the report."""
    portal = portal_config.get(key)
    if portal is not None:
        return list(portal.urls)
    # A stand-in swapped into MODULES by a test, or a module holding its own
    # spec. The file is asked first because it is the source of truth.
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
