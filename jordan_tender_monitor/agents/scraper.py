"""
Scraper agent: run every enabled portal and record how each one fared.

A failing portal must never abort the run. It is skipped, its reason is
diagnosed and kept, and it is reported as unavailable with the URL to check by
hand. The distinction between "this portal worked and found nothing" and "this
portal could not be read" is carried all the way through to the email subject
line -- collapsing the two is how a dead monitor goes unnoticed for weeks.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from .. import config, portal_config, portals
from ..portals import base as base_module
from ..portals.base import PortalError

log = logging.getLogger(__name__)


@dataclass
class PortalHealth:
    key: str
    name: str
    tier: int
    status: str              # "ok" | "unavailable" | "unconfigured" | "no listing"
    count: int = 0
    # Notices the portal returned BEFORE Jordan filtering. None when the portal
    # is inherently Jordan-specific and never filters. "OK: 0" is ambiguous on
    # its own -- returned nothing, or returned 500 worldwide notices of which
    # none were Jordan? Those need entirely different fixes.
    scanned: int | None = None
    reason: str = ""
    urls: list[str] = field(default_factory=list)
    layer: str = ""
    quality: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def broken(self) -> bool:
        """Unconfigured and no-listing are not broken.

        SAM.gov needs an API key whose approval takes weeks. Reporting a
        paperwork delay as a scraper failure would cry wolf for a month and
        train the reader to ignore the alert that matters.

        "No listing" is the same argument for a different cause. JICA's Jordan
        office publishes no procurement page at all -- verified, both URL
        schemes 404 while Bangladesh and Indonesia answer on both. A source
        that has nothing to read is not a scraper that has stopped working,
        and reporting it as one puts a permanent red line in every report.
        """
        return self.status == "unavailable"


@dataclass
class ScrapeResult:
    records: list[dict]
    health: list[PortalHealth]

    @property
    def ok_portals(self) -> list[PortalHealth]:
        return [h for h in self.health if h.ok]

    @property
    def broken_portals(self) -> list[PortalHealth]:
        return [h for h in self.health if h.broken]

    @property
    def unconfigured_portals(self) -> list[PortalHealth]:
        return [h for h in self.health if h.status == "unconfigured"]

    @property
    def no_listing_portals(self) -> list[PortalHealth]:
        return [h for h in self.health if h.status == "no listing"]

    @property
    def all_broken(self) -> bool:
        considered = [h for h in self.health
                      if h.status not in ("unconfigured", "no listing")]
        return bool(considered) and all(h.broken for h in considered)


def _run_one(key: str, module) -> PortalHealth:
    health = PortalHealth(
        key=key,
        name=portals.name(key),
        tier=portals.tier(key),
        status="ok",
        urls=portals.source_urls(key),
    )
    try:
        records = module.fetch_tenders()
    except PortalError as exc:
        reason = exc.reason
        if reason.startswith("not configured"):
            health.status = "unconfigured"
        elif reason.startswith("no listing published"):
            health.status = "no listing"
        else:
            health.status = "unavailable"
        health.reason = reason
        if exc.url and exc.url not in health.urls:
            health.urls.insert(0, exc.url)
        log.warning("portal %s %s: %s", key, health.status, reason)
        return health
    except Exception as exc:  # noqa: BLE001 -- one portal must not kill the run
        health.status = "unavailable"
        health.reason = f"unexpected {type(exc).__name__}: {exc}"
        log.exception("portal %s raised unexpectedly", key)
        return health

    health.count = len(records)
    health.scanned = base_module.take_scanned()
    if records:
        health.layer = records[0].get("_layer", "")
        health.quality = records[0].get("_quality", 0.0)
    health._records = records  # type: ignore[attr-defined]
    return health


def _config_health(only: list[str] | None = None) -> list[PortalHealth]:
    """A status line for every portal portals.json could not give us.

    A rejected entry is skipped, and a skipped portal that said nothing would
    simply vanish from the report -- which is the failure this codebase keeps
    finding, dressed as configuration. It reports as unavailable, with the
    file's own diagnosis as the reason, so a typo pushed from a phone is
    visible in the same table as a bot wall.

    A file that could not be read at all is one line rather than thirteen,
    because that is the honest description: nothing was configured, so nothing
    can be said about any individual portal.
    """
    registry = portal_config.REGISTRY
    out = [PortalHealth(key=problem.key, name=f"{problem.key} (portals.json)",
                        tier=2, status="unavailable",
                        reason=f"portals.json rejected this entry: {problem.message}",
                        urls=[registry.path])
           for problem in registry.problems
           if not only or problem.key in only]
    if registry.fatal:
        out.insert(0, PortalHealth(
            key="portals.json", name="portals.json", tier=1,
            status="unavailable",
            reason=f"the portal list {registry.fatal}. No portal could be "
                   f"configured, so nothing was read this run",
            urls=[registry.path]))
    return out


def scrape(only: list[str] | None = None) -> ScrapeResult:
    """Poll every enabled portal in parallel and collect the results."""
    selected = portals.enabled()
    if only:
        selected = {k: v for k, v in selected.items() if k in only}

    records: list[dict] = []
    health: list[PortalHealth] = _config_health(only)

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
        futures = {pool.submit(_run_one, key, module): key
                   for key, module in selected.items()}
        for future in as_completed(futures):
            result = future.result()
            health.append(result)
            records.extend(getattr(result, "_records", []))

    order = list(portals.MODULES)
    health.sort(key=lambda h: order.index(h.key) if h.key in order else 99)
    return ScrapeResult(records=records, health=health)


def check_portals() -> list[PortalHealth]:
    """Reachability check only -- fetch each portal and report, parse nothing.

    Used by --check-portals to answer "can this machine even see these sites?"
    before anything else is debugged.
    """
    return scrape().health
