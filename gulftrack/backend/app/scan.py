"""The scan runner.

Responsibilities, in the order they matter:

1. Refuse to run twice at once. Replit's Scheduled Deployments impose no
   concurrency limit, so an overrunning scan gets a second scan started
   alongside it. Both would write the same postings and corrupt the counts.
2. Isolate adapters. One portal redesigning its HTML must degrade that source
   and nothing else. A raising adapter never aborts a scan.
3. Never invent a record. A failed adapter contributes zero postings and says
   why; it does not contribute a plausible-looking guess.
4. Leave the evidence behind. Every run records which sources were attempted,
   what each returned, and what broke, because the home screen has to be able
   to tell Fadi that four of nine adapters failed last night.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.base import AccessMode, JobPosting, SourceAdapter
from app.models import AccessMode as DbAccessMode
from app.models import (
    Contact, Job, JobScore, ScanLock, ScanRun, ScanStatus, Source, SourceRun,
    utcnow,
)
from app.scoring.engine import ScoringEngine

log = logging.getLogger("gulftrack.scan")

# A lock older than this belonged to a run that died without releasing it.
# Replit caps a scheduled job at 11 hours; anything past that is certainly dead,
# and in practice a scan of this size finishing in under an hour means two is
# already generous.
STALE_LOCK_AFTER = timedelta(hours=2)


class ScanSkipped(RuntimeError):
    """Another scan holds the lock. Not an error — the guard working."""


@dataclass(slots=True)
class ScanSummary:
    scan_run_id: int | None
    status: ScanStatus
    sources_attempted: int = 0
    sources_failed: int = 0
    postings_seen: int = 0
    postings_new: int = 0
    failed_sources: tuple[str, ...] = ()
    note: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in (ScanStatus.OK, ScanStatus.PARTIAL)

    def describe(self) -> str:
        """Plain language, because this text reaches the home screen."""
        if self.status is ScanStatus.SKIPPED:
            return "Scan skipped — another scan was still running."
        if self.status is ScanStatus.FAILED:
            return f"Scan failed. {self.note or ''}".strip()
        parts = [
            f"{self.postings_seen} postings seen",
            f"{self.postings_new} new",
            f"{self.sources_attempted - self.sources_failed}"
            f"/{self.sources_attempted} sources healthy",
        ]
        line = ", ".join(parts) + "."
        if self.failed_sources:
            line += f" Failed: {', '.join(self.failed_sources)}."
        return line


# --------------------------------------------------------------------------
# The lock
# --------------------------------------------------------------------------

def acquire_lock(
    session: Session, scan_run_id: int, holder: str, now: datetime
) -> bool:
    """Take the single-row lock, breaking it only if it is provably stale.

    Returns False when another scan legitimately holds it. The caller records a
    skipped run rather than silently doing nothing — a scan that never happens
    must be visible.
    """
    existing = session.get(ScanLock, 1)
    if existing is not None:
        age = now - _aware(existing.acquired_at)
        if age < STALE_LOCK_AFTER:
            return False
        log.warning(
            "Breaking stale scan lock held by run %s for %s",
            existing.scan_run_id, age,
        )
        session.delete(existing)
        session.flush()

    session.add(ScanLock(
        id=1, scan_run_id=scan_run_id, acquired_at=now, holder=holder,
    ))
    try:
        session.flush()
    except IntegrityError:
        # Another process inserted between our check and our write. The
        # database, not our reasoning, is the arbiter.
        session.rollback()
        return False
    return True


def release_lock(session: Session, scan_run_id: int) -> None:
    lock = session.get(ScanLock, 1)
    if lock is not None and lock.scan_run_id == scan_run_id:
        session.delete(lock)
        session.flush()


def _aware(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat them as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

def upsert_posting(session: Session, posting: JobPosting, now: datetime) -> bool:
    """Store or refresh one posting. Returns True if it is new to us."""
    existing = session.get(Job, posting.fingerprint)
    if existing is None:
        session.add(Job(
            fingerprint=posting.fingerprint,
            source_id=posting.source_id,
            source_job_id=posting.source_job_id,
            title=posting.title,
            employer=posting.employer,
            url=posting.url,
            description=posting.description,
            location=posting.location,
            posted_date=posting.posted_date,
            closing_date=posting.closing_date,
            salary_raw=posting.salary_raw,
            salary_min=posting.salary_min,
            salary_max=posting.salary_max,
            salary_currency=posting.salary_currency,
            language=posting.language,
            first_seen_at=now,
            last_seen_at=now,
            still_listed=True,
        ))
        return True

    # A live posting can be edited by the employer — a closing date added, the
    # description expanded. Refresh the mutable fields, keep first_seen_at.
    existing.title = posting.title
    existing.employer = posting.employer
    existing.url = posting.url
    existing.description = posting.description
    existing.location = posting.location
    existing.posted_date = posting.posted_date
    existing.closing_date = posting.closing_date
    existing.salary_raw = posting.salary_raw
    existing.salary_min = posting.salary_min
    existing.salary_max = posting.salary_max
    existing.salary_currency = posting.salary_currency
    existing.language = posting.language
    existing.last_seen_at = now
    existing.still_listed = True
    return False


def store_score(
    session: Session, fingerprint: str, result, now: datetime
) -> None:
    row = session.get(JobScore, fingerprint) or JobScore(fingerprint=fingerprint)
    row.score = result.score
    row.raw_score = result.raw_score
    row.band = result.band
    row.lane = result.lane
    row.employer_tier = result.employer_tier
    row.breakdown = [
        {
            "signal_id": c.signal_id,
            "label": c.label,
            "contribution": c.contribution,
            "matched": list(c.matched),
        }
        for c in result.components
    ]
    row.flags = list(result.flags)
    row.excluded = result.excluded
    row.exclusion_reason = (
        "; ".join(e.label for e in result.exclusions) if result.exclusions else None
    )
    row.suppressed = result.suppressed
    row.suppression_reason = result.suppression_reason
    row.warm_route = result.warm_route
    row.warm_contact_count = result.warm_contact_count
    row.scored_at = now
    session.add(row)


def warm_contact_counts(
    session: Session, postings: Sequence[JobPosting]
) -> dict[str, int]:
    """How many known contacts sit inside each posting's employer.

    Matched on the contact's `target_employer`, which is set by hand — an
    imported contact list never carries it, and inferring it from a free-text
    employer string would manufacture warm routes that do not exist.
    """
    if not postings:
        return {}

    rows = session.execute(
        select(Contact.target_employer).where(Contact.target_employer.is_not(None))
    ).scalars().all()
    if not rows:
        return {}

    tally: dict[str, int] = {}
    for target in rows:
        key = target.strip().casefold()
        tally[key] = tally.get(key, 0) + 1

    counts: dict[str, int] = {}
    for posting in postings:
        employer = posting.employer.strip().casefold()
        hits = 0
        for key, n in tally.items():
            # Substring both ways: "Diriyah" the contact tag should match
            # "Diriyah Company" the posting employer, and vice versa.
            if key and (key in employer or employer in key):
                hits += n
        if hits:
            counts[posting.fingerprint] = hits
    return counts


# --------------------------------------------------------------------------
# The runner
# --------------------------------------------------------------------------

def run_scan(
    session: Session,
    adapters: Iterable[SourceAdapter],
    engine: ScoringEngine,
    *,
    holder: str = "scheduler",
    now_fn: Callable[[], datetime] = utcnow,
) -> ScanSummary:
    """Run every adapter once, score what comes back, record what happened."""
    now = now_fn()
    scan = ScanRun(started_at=now, status=ScanStatus.RUNNING)
    session.add(scan)
    session.flush()

    if not acquire_lock(session, scan.id, holder, now):
        scan.status = ScanStatus.SKIPPED
        scan.finished_at = now
        scan.note = "Another scan was still running when this one was due."
        session.commit()
        log.warning("Scan %s skipped: lock held", scan.id)
        return ScanSummary(scan.id, ScanStatus.SKIPPED, note=scan.note)

    try:
        return _execute(session, scan, adapters, engine, now_fn)
    finally:
        release_lock(session, scan.id)
        session.commit()


def _execute(
    session: Session,
    scan: ScanRun,
    adapters: Iterable[SourceAdapter],
    engine: ScoringEngine,
    now_fn: Callable[[], datetime],
) -> ScanSummary:
    collected: list[JobPosting] = []
    failed: list[str] = []
    attempted = 0
    healthy_source_ids: list[str] = []
    seen_by_source: dict[str, set[str]] = {}

    for adapter in adapters:
        if getattr(adapter, "access_mode", AccessMode.FETCH) == AccessMode.DEEP_LINK:
            # Deep-link sources are opened by a human; there is nothing to fetch
            # and counting them as an attempt would misreport source health.
            continue

        attempted += 1
        source = _ensure_source(session, adapter)
        if not source.enabled:
            attempted -= 1
            continue

        started = time.monotonic()
        try:
            postings = list(adapter.fetch())
        except Exception as exc:  # one bad adapter must never abort the scan
            elapsed = int((time.monotonic() - started) * 1000)
            message = f"{type(exc).__name__}: {exc}"
            log.exception("Adapter %s failed", adapter.source_id)
            source.record_failure(message, now_fn())
            session.add(SourceRun(
                scan_run_id=scan.id, source_id=adapter.source_id, ok=False,
                postings_returned=0, error=message, duration_ms=elapsed,
            ))
            failed.append(adapter.source_id)
            continue

        elapsed = int((time.monotonic() - started) * 1000)
        wrong_source = [p for p in postings if p.source_id != adapter.source_id]
        if wrong_source:
            # Defensive: a copy-pasted adapter that reports another source's id
            # would silently overwrite that source's postings.
            message = (
                f"returned {len(wrong_source)} postings labelled with another "
                f"source id"
            )
            source.record_failure(message, now_fn())
            session.add(SourceRun(
                scan_run_id=scan.id, source_id=adapter.source_id, ok=False,
                postings_returned=0, error=message, duration_ms=elapsed,
            ))
            failed.append(adapter.source_id)
            continue

        source.record_success(len(postings), now_fn())
        session.add(SourceRun(
            scan_run_id=scan.id, source_id=adapter.source_id, ok=True,
            postings_returned=len(postings), duration_ms=elapsed,
        ))
        healthy_source_ids.append(adapter.source_id)
        seen_by_source[adapter.source_id] = {p.fingerprint for p in postings}
        collected.extend(postings)

    # Deduplicate within the run: two adapters can legitimately surface the same
    # posting. First one wins; the ordering of adapters is the priority.
    unique: dict[str, JobPosting] = {}
    for posting in collected:
        unique.setdefault(posting.fingerprint, posting)

    now = now_fn()
    new_count = 0
    for posting in unique.values():
        if upsert_posting(session, posting, now):
            new_count += 1
    session.flush()

    warm = warm_contact_counts(session, list(unique.values()))
    for posting in unique.values():
        store_score(session, posting.fingerprint, engine.score(
            posting, warm.get(posting.fingerprint, 0)
        ), now)

    _retire_unseen(session, healthy_source_ids, seen_by_source)

    if failed and not healthy_source_ids:
        status = ScanStatus.FAILED
    elif failed:
        status = ScanStatus.PARTIAL
    else:
        status = ScanStatus.OK

    scan.status = status
    scan.finished_at = now
    scan.sources_attempted = attempted
    scan.sources_failed = len(failed)
    scan.postings_seen = len(unique)
    scan.postings_new = new_count
    session.flush()

    return ScanSummary(
        scan_run_id=scan.id,
        status=status,
        sources_attempted=attempted,
        sources_failed=len(failed),
        postings_seen=len(unique),
        postings_new=new_count,
        failed_sources=tuple(failed),
    )


def _retire_unseen(
    session: Session,
    healthy_source_ids: Sequence[str],
    seen_by_source: dict[str, set[str]],
) -> None:
    """Mark postings a healthy source stopped listing.

    Only healthy sources may retire their postings. If an adapter broke, its
    jobs stay listed rather than silently vanishing — a broken scraper is not
    evidence that a job closed. This is the "last known good" behaviour from
    section 17: degrade to stale data, never to an empty feed that looks real.
    """
    for source_id in healthy_source_ids:
        seen = seen_by_source.get(source_id, set())
        rows = session.execute(
            select(Job).where(Job.source_id == source_id, Job.still_listed.is_(True))
        ).scalars().all()
        for job in rows:
            if job.fingerprint not in seen:
                job.still_listed = False


def _ensure_source(session: Session, adapter: SourceAdapter) -> Source:
    source = session.get(Source, adapter.source_id)
    if source is None:
        source = Source(
            id=adapter.source_id,
            display_name=getattr(adapter, "display_name", adapter.source_id),
            tier=int(getattr(adapter, "tier", 2)),
            access_mode=DbAccessMode(
                str(getattr(adapter, "access_mode", AccessMode.FETCH).value)
            ),
            repair_note=getattr(adapter, "repair_note", ""),
            tos_basis=getattr(adapter, "tos_basis", None),
        )
        session.add(source)
        session.flush()
    return source
