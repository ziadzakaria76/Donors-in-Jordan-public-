"""Database schema.

Two shapes here deserve explanation.

Postings and scores are separate tables. A posting is what a source said; a
score is what the current profile makes of it. Keeping them apart means
changing a weight in Settings re-scores history without re-fetching anything,
and a scan that finds nothing new can still reflect a profile change.

Source health is a first-class table, not a log. Section 17 assumes this system
decays — portals redesign, endpoints move — and that Fadi cannot fix it
himself. So every adapter's last success, consecutive failures and last error
are queryable state that the home screen reads directly.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------
# Sources and their health
# --------------------------------------------------------------------------

class AccessMode(str, enum.Enum):
    FETCH = "fetch"
    DEEP_LINK = "deep_link"


class Source(Base):
    """One configured source and everything known about its condition."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200))
    tier: Mapped[int] = mapped_column(Integer)
    access_mode: Mapped[AccessMode] = mapped_column(
        Enum(AccessMode, native_enum=False), default=AccessMode.FETCH
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Plain-language note for whoever repairs this in six months (section 17).
    repair_note: Mapped[str] = mapped_column(Text, default="")
    # For deep-link sources: why we do not scrape, quoted from their terms.
    tos_basis: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_posting_count: Mapped[int] = mapped_column(Integer, default=0)

    BROKEN_AFTER_FAILURES = 3

    @property
    def broken(self) -> bool:
        """Three strikes. After this we stop retrying silently and say so."""
        return self.consecutive_failures >= self.BROKEN_AFTER_FAILURES

    def record_success(self, count: int, at: datetime) -> None:
        self.last_attempt_at = at
        self.last_success_at = at
        self.last_posting_count = count
        self.consecutive_failures = 0
        self.last_error = None

    def record_failure(self, error: str, at: datetime) -> None:
        self.last_attempt_at = at
        self.last_error = error[:2000]
        self.consecutive_failures += 1


# --------------------------------------------------------------------------
# Scans
# --------------------------------------------------------------------------

class ScanStatus(str, enum.Enum):
    RUNNING = "running"
    OK = "ok"
    PARTIAL = "partial"   # some adapters failed; the scan still produced results
    FAILED = "failed"
    SKIPPED = "skipped"   # refused to start because another scan held the lock


class ScanLock(Base):
    """The overlap guard.

    Replit's Scheduled Deployments have no concurrency limit: if a scan overruns
    its interval, Replit starts another one alongside it. Two scans writing the
    same postings duplicate work and corrupt counts. A single-row table with a
    fixed primary key makes the guard the database's problem — the second
    INSERT simply fails, on Postgres and SQLite alike.
    """

    __tablename__ = "scan_lock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    scan_run_id: Mapped[int] = mapped_column(Integer)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    holder: Mapped[str] = mapped_column(String(200), default="")


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, native_enum=False), default=ScanStatus.RUNNING
    )
    sources_attempted: Mapped[int] = mapped_column(Integer, default=0)
    sources_failed: Mapped[int] = mapped_column(Integer, default=0)
    postings_seen: Mapped[int] = mapped_column(Integer, default=0)
    postings_new: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_runs: Mapped[list["SourceRun"]] = relationship(
        back_populates="scan_run", cascade="all, delete-orphan"
    )


class SourceRun(Base):
    """One adapter's outcome within one scan."""

    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_run_id: Mapped[int] = mapped_column(ForeignKey("scan_runs.id"))
    source_id: Mapped[str] = mapped_column(String(64))
    ok: Mapped[bool] = mapped_column(Boolean)
    postings_returned: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    scan_run: Mapped[ScanRun] = relationship(back_populates="source_runs")


# --------------------------------------------------------------------------
# Postings
# --------------------------------------------------------------------------

class Job(Base):
    """A posting exactly as the source reported it.

    Nothing derived lives here. A field is None because the source did not say,
    never because a default looked tidier.
    """

    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source_id", "source_job_id"),)

    fingerprint: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    source_job_id: Mapped[str] = mapped_column(String(200))

    title: Mapped[str] = mapped_column(String(400))
    employer: Mapped[str] = mapped_column(String(300), index=True)
    url: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    salary_raw: Mapped[str | None] = mapped_column(String(300), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # False once a scan of a healthy source stops returning it. Never deleted —
    # an application in the tracker must still resolve to the job it was for.
    still_listed: Mapped[bool] = mapped_column(Boolean, default=True)

    score: Mapped["JobScore | None"] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )


class JobScore(Base):
    """The current profile's verdict on a posting.

    Stored rather than computed on read so the feed sorts in the database, and
    so a score the user disagreed with can be compared against the score after
    they changed the weight.
    """

    __tablename__ = "job_scores"

    fingerprint: Mapped[str] = mapped_column(
        ForeignKey("jobs.fingerprint"), primary_key=True
    )
    score: Mapped[int] = mapped_column(Integer, index=True)
    raw_score: Mapped[int] = mapped_column(Integer, index=True)
    band: Mapped[str] = mapped_column(String(16))
    lane: Mapped[str | None] = mapped_column(String(4), nullable=True)
    employer_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # The named signals and their contributions, as shown on the card.
    breakdown: Mapped[list] = mapped_column(JSON, default=list)
    flags: Mapped[list] = mapped_column(JSON, default=list)

    excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    suppression_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    warm_route: Mapped[bool] = mapped_column(Boolean, default=False)
    warm_contact_count: Mapped[int] = mapped_column(Integer, default=0)

    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="score")


# --------------------------------------------------------------------------
# Network (section 8). Present from the start so warm-route linkage can ship
# with the feed at M2 rather than waiting for the full module at M6.
# --------------------------------------------------------------------------

class Contact(Base):
    """A person Fadi knows.

    Deliberately thin, per section 10: enough to route a warm introduction and
    nothing more. No home address, no personal phone unless entered by hand, no
    enrichment from data brokers.
    """

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    employer: Mapped[str | None] = mapped_column(String(300), index=True, nullable=True)
    role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    how_connected: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which target employer on the profile list this person sits inside. This is
    # the field that makes warm-route linkage work, and no contact export
    # contains it — it is set by hand.
    target_employer: Mapped[str | None] = mapped_column(String(300), index=True, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
