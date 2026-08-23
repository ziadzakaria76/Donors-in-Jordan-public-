"""Run orchestration: collect, gate, dedupe, filter, screen, score."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from .classify import Classifier
from .config import Config
from .dates import is_open
from .fetch import Fetcher
from .gate import CountryGate
from .matching import CountryMatcher
from .models import INSIDE, LINK_TYPES, Tender
from .portals import REGISTRY
from .portals.base import PortalOutcome
from .scoring import score_batch
from .screening import DISCLAIMER, Screener, ScreeningUnavailable

_WS = re.compile(r"\s+")


@dataclass
class RunResult:
    started: str
    tenders: list[Tender] = field(default_factory=list)          # in scope
    excluded: list[Tender] = field(default_factory=list)         # out of scope, kept for audit
    portals: list[PortalOutcome] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    screening_status: list[dict] = field(default_factory=list)
    screening_error: Optional[str] = None
    duplicates_collapsed: int = 0
    expired_dropped: int = 0

    # ---------------------------------------------------------------- health
    @property
    def available(self) -> list[PortalOutcome]:
        return [p for p in self.portals if p.available and not p.skipped_reason]

    @property
    def failed(self) -> list[PortalOutcome]:
        return [p for p in self.portals if not p.available]

    @property
    def skipped(self) -> list[PortalOutcome]:
        return [p for p in self.portals if p.skipped_reason]

    @property
    def new_tenders(self) -> list[Tender]:
        return [t for t in self.tenders if t.is_new]

    def subject(self) -> str:
        """Portal health goes in the subject line.

        If the subject says "0 opportunities" whether every portal failed or
        every portal worked and nothing matched, a dead monitor goes unnoticed
        for weeks.
        """
        total = len(self.portals) - len(self.skipped)
        if total and not self.available:
            return "ACTION NEEDED: all portals unreachable -- no data this run"
        new, live = len(self.new_tenders), len(self.tenders)
        head = (f"Syria tenders -- {new} new, {live} open" if new
                else f"Syria tenders -- no new opportunities, {live} open")
        if self.failed:
            names = ", ".join(p.label for p in self.failed)
            return f"{head} | WARNING: {len(self.failed)} portal(s) down ({names})"
        return f"{head} | all {len(self.available)} portals OK"


def _dedupe_key(tender: Tender) -> str:
    title = _WS.sub(" ", (tender.title or "").strip().lower())
    closing = tender.closing_date.isoformat() if tender.closing_date else ""
    return f"{title}|{closing}"


def run(cfg: Config, fetcher: Optional[Fetcher] = None, screener: Optional[Screener] = None,
        store=None, today: Optional[date] = None, portals: Optional[list[str]] = None) -> RunResult:
    profile = cfg.profile
    today = today or date.today()
    fetcher = fetcher or Fetcher()
    matcher = CountryMatcher(profile)
    gate = CountryGate(profile, matcher, Classifier(profile, matcher))

    result = RunResult(started=datetime.now(timezone.utc).isoformat(timespec="seconds"))

    # 1. collect. A failing portal is skipped and reported, never fatal.
    collected: list[Tender] = []
    for name in (portals or cfg.enabled_portals):
        portal_cls = REGISTRY.get(name)
        if portal_cls is None:
            continue
        outcome = portal_cls(cfg.portal_cfg(name), profile, fetcher, gate).collect()
        result.portals.append(outcome)
        collected.extend(outcome.tenders)

    # 2. counts across every category, including the ones out of scope: a single
    #    total says nothing about whether the classifier is working.
    result.counts = {key: 0 for key in LINK_TYPES}
    for outcome in result.portals:
        for link_type, count in outcome.stats.link_types.items():
            result.counts[link_type] = result.counts.get(link_type, 0) + count

    # 3. dedupe across portals
    unique: dict[str, Tender] = {}
    for tender in collected:
        key = _dedupe_key(tender)
        existing = unique.get(key)
        if existing is None:
            unique[key] = tender
        else:
            existing.add_flag(f"also_on:{tender.portal}")
            result.duplicates_collapsed += 1
    deduped = list(unique.values())

    # 4. deadline filter. Expired out; no published deadline kept and flagged;
    #    a deadline of today counts as open.
    open_tenders = []
    for tender in deduped:
        if is_open(tender.closing_date, today):
            open_tenders.append(tender)
        else:
            result.expired_dropped += 1

    # 5. scope. Out-of-scope tenders are kept for audit, never silently dropped.
    included = set(cfg.included_link_types)
    for tender in open_tenders:
        (result.tenders if tender.syria_link_type in included else result.excluded).append(tender)

    # 6. screening -- flags only, never exclusion.
    if screener is not None:
        try:
            screener.load()
            for tender in result.tenders:
                hits = screener.screen([tender.contact, tender.description and None,
                                        (tender.country_fields or {}).get("buyer_name")])
                if hits:
                    tender.screening = hits
                    tender.add_flag("sanctions_flag")
            result.screening_status = screener.list_status()
        except ScreeningUnavailable as exc:
            result.screening_error = f"{exc} ({DISCLAIMER})"

    # 7. rank, then mark what is new
    score_batch(result.tenders, profile, today)
    result.tenders.sort(key=lambda t: (-t.score, t.closing_date or date.max))
    if store is not None:
        store.mark_new(result.tenders)
    return result


def scope_summary(result: RunResult) -> str:
    parts = [f"{key}={result.counts.get(key, 0)}" for key in LINK_TYPES]
    return "classification: " + ", ".join(parts) + \
           f" | in scope: {len(result.tenders)} | excluded but logged: {len(result.excluded)}"


__all__ = ["RunResult", "run", "scope_summary", "INSIDE"]
