"""
Agent 1 -- portal scrapers.

Runs every enabled portal module in a bounded thread pool and returns both the
raw tenders and a per-portal status record. A portal that fails never aborts the
run: the error is captured and surfaced in the report as
"Portal X unavailable - check manually".
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
import portals

log = logging.getLogger(__name__)


class PortalStatus(dict):
    """Per-portal outcome. A plain dict so it serialises straight to JSON."""

    @property
    def ok(self) -> bool:
        return bool(self["ok"])


def _run_one(portal_key: str) -> tuple[list[dict], PortalStatus]:
    name = config.PORTAL_NAMES.get(portal_key, portal_key)
    started = time.monotonic()
    status = PortalStatus(
        key=portal_key, name=name, ok=False, count=0, error=None, seconds=0.0
    )
    try:
        module = portals.load(portal_key)
        tenders = module.fetch_tenders() or []
        status["ok"] = True
        status["count"] = len(tenders)
        log.info("%s: OK, %d tenders in %.1fs", name, len(tenders), time.monotonic() - started)
        return tenders, status
    except Exception as exc:  # noqa: BLE001 - one portal must never kill the run
        message = str(exc).strip() or exc.__class__.__name__
        status["error"] = message[:400]
        log.warning("%s: FAILED - %s", name, message[:400])
        return [], status
    finally:
        status["seconds"] = round(time.monotonic() - started, 1)


def scrape_all(portal_keys: list[str] | None = None) -> tuple[list[dict], list[PortalStatus]]:
    """Scrape every enabled portal in parallel."""
    keys = portal_keys or [
        key for key in portals.PORTAL_MODULES if config.ENABLED_PORTALS.get(key, False)
    ]
    log.info("Scraping %d portals with %d workers", len(keys), config.MAX_WORKERS)

    all_tenders: list[dict] = []
    statuses: list[PortalStatus] = []

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
        futures = {pool.submit(_run_one, key): key for key in keys}
        for future in as_completed(futures):
            tenders, status = future.result()
            all_tenders.extend(tenders)
            statuses.append(status)

    # Keep report ordering stable and predictable
    order = {key: i for i, key in enumerate(portals.PORTAL_MODULES)}
    statuses.sort(key=lambda s: order.get(s["key"], 999))

    ok = sum(1 for s in statuses if s["ok"])
    log.info(
        "Scrape complete: %d raw tenders, %d/%d portals succeeded",
        len(all_tenders), ok, len(statuses),
    )
    return all_tenders, statuses
