"""Scan runner behaviour.

The adapters here are stubs. They return fixture postings so the runner's
control flow can be exercised — the postings never leave this file.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.adapters.base import AccessMode, JobPosting, SourceTier
from app.models import (
    Base, Contact, Job, ScanLock, ScanRun, ScanStatus, Source, SourceRun, utcnow,
)
from app.scan import STALE_LOCK_AFTER, run_scan, warm_contact_counts
from app.scoring.engine import ScoringEngine
from app.scoring.profile import load_profile


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(scope="module")
def scorer():
    return ScoringEngine(load_profile())


class StubAdapter:
    """A source that returns whatever it was handed, or raises."""

    tier = SourceTier.STRUCTURED
    access_mode = AccessMode.FETCH
    repair_note = "stub"

    def __init__(self, source_id, postings=None, error=None):
        self.source_id = source_id
        self.display_name = source_id
        self._postings = postings or []
        self._error = error
        self.calls = 0

    def fetch(self):
        self.calls += 1
        if self._error:
            raise self._error
        return list(self._postings)


class DeepLinkAdapter(StubAdapter):
    access_mode = AccessMode.DEEP_LINK

    def fetch(self):
        raise AssertionError("a deep-link source must never be fetched")


def job(source_id="src-a", jid="1", **kw):
    base = dict(
        source_id=source_id,
        source_job_id=jid,
        title="Operations Director",
        employer="Nesma & Partners",
        url=f"https://example.com/{source_id}/{jid}",
        location="Riyadh",
    )
    base.update(kw)
    return JobPosting(**base)


# -- the overlap lock --------------------------------------------------------

def test_a_second_scan_refuses_to_start_and_says_so(session, scorer):
    adapter = StubAdapter("src-a", [job()])
    first = run_scan(session, [adapter], scorer)
    assert first.status is ScanStatus.OK

    # Simulate a scan still in flight when the next one is due.
    session.add(ScanLock(id=1, scan_run_id=first.scan_run_id, acquired_at=utcnow()))
    session.flush()

    second_adapter = StubAdapter("src-a", [job(jid="2")])
    second = run_scan(session, [second_adapter], scorer)

    assert second.status is ScanStatus.SKIPPED
    assert second_adapter.calls == 0, "a skipped scan must not fetch anything"
    assert "still running" in second.describe()

    # The skip is recorded, not swallowed — silence is what we are avoiding.
    runs = session.execute(
        select(ScanRun).where(ScanRun.status == ScanStatus.SKIPPED)
    ).scalars().all()
    assert len(runs) == 1 and runs[0].note


def test_a_stale_lock_from_a_dead_run_is_broken(session, scorer):
    session.add(ScanLock(
        id=1, scan_run_id=999,
        acquired_at=utcnow() - STALE_LOCK_AFTER - timedelta(minutes=1),
    ))
    session.flush()

    adapter = StubAdapter("src-a", [job()])
    result = run_scan(session, [adapter], scorer)

    assert result.status is ScanStatus.OK
    assert adapter.calls == 1


def test_the_lock_is_released_even_when_everything_fails(session, scorer):
    run_scan(session, [StubAdapter("src-a", error=RuntimeError("boom"))], scorer)
    assert session.get(ScanLock, 1) is None, "a failed scan must not wedge the lock"


# -- adapter isolation -------------------------------------------------------

def test_one_broken_adapter_does_not_stop_the_others(session, scorer):
    good = StubAdapter("good", [job("good", "1"), job("good", "2")])
    bad = StubAdapter("bad", error=ValueError("portal redesigned"))
    other = StubAdapter("other", [job("other", "1")])

    result = run_scan(session, [good, bad, other], scorer)

    assert result.status is ScanStatus.PARTIAL
    assert result.sources_attempted == 3
    assert result.sources_failed == 1
    assert result.failed_sources == ("bad",)
    assert result.postings_seen == 3
    assert good.calls == 1 and other.calls == 1
    assert "Failed: bad" in result.describe()


def test_a_failed_adapter_contributes_no_postings(session, scorer):
    run_scan(session, [StubAdapter("bad", error=RuntimeError("502"))], scorer)
    assert session.execute(select(Job)).scalars().all() == []


def test_total_failure_is_reported_as_failed_not_as_an_empty_success(session, scorer):
    result = run_scan(session, [StubAdapter("bad", error=RuntimeError("x"))], scorer)
    assert result.status is ScanStatus.FAILED


def test_an_adapter_mislabelling_its_postings_is_rejected(session, scorer):
    """A copy-pasted adapter must not overwrite another source's jobs."""
    liar = StubAdapter("liar", [job(source_id="someone-else", jid="1")])
    result = run_scan(session, [liar], scorer)

    assert result.status is ScanStatus.FAILED
    assert session.execute(select(Job)).scalars().all() == []
    source = session.get(Source, "liar")
    assert "another source id" in source.last_error


def test_deep_link_sources_are_never_fetched_or_counted(session, scorer):
    result = run_scan(
        session, [DeepLinkAdapter("bayt"), StubAdapter("src-a", [job()])], scorer,
    )
    assert result.sources_attempted == 1
    assert result.status is ScanStatus.OK


# -- source health -----------------------------------------------------------

def test_three_consecutive_failures_marks_a_source_broken(session, scorer):
    adapter = StubAdapter("flaky", error=RuntimeError("timeout"))
    for _ in range(3):
        run_scan(session, [adapter], scorer)

    source = session.get(Source, "flaky")
    assert source.consecutive_failures == 3
    assert source.broken
    assert source.last_error


def test_a_success_clears_the_failure_streak(session, scorer):
    run_scan(session, [StubAdapter("s", error=RuntimeError("x"))], scorer)
    run_scan(session, [StubAdapter("s", [job("s", "1")])], scorer)

    source = session.get(Source, "s")
    assert source.consecutive_failures == 0
    assert source.last_error is None
    assert source.last_success_at is not None
    assert source.last_posting_count == 1


def test_every_source_run_is_recorded_for_the_health_screen(session, scorer):
    run_scan(
        session,
        [StubAdapter("a", [job("a", "1")]), StubAdapter("b", error=OSError("dns"))],
        scorer,
    )
    runs = {r.source_id: r for r in session.execute(select(SourceRun)).scalars()}
    assert runs["a"].ok and runs["a"].postings_returned == 1
    assert not runs["b"].ok and "dns" in runs["b"].error


# -- postings ----------------------------------------------------------------

def test_new_postings_are_counted_once_and_only_once(session, scorer):
    postings = [job("a", "1"), job("a", "2")]
    first = run_scan(session, [StubAdapter("a", postings)], scorer)
    second = run_scan(session, [StubAdapter("a", postings)], scorer)

    assert first.postings_new == 2
    assert second.postings_new == 0
    assert second.postings_seen == 2


def test_the_same_posting_from_two_sources_is_stored_once(session, scorer):
    shared = job("a", "1")
    result = run_scan(
        session, [StubAdapter("a", [shared]), StubAdapter("b", [shared])], scorer,
    )
    assert result.postings_seen == 1
    assert len(session.execute(select(Job)).scalars().all()) == 1


def test_a_healthy_source_retires_a_posting_it_stopped_listing(session, scorer):
    run_scan(session, [StubAdapter("a", [job("a", "1"), job("a", "2")])], scorer)
    run_scan(session, [StubAdapter("a", [job("a", "1")])], scorer)

    jobs = {j.source_job_id: j for j in session.execute(select(Job)).scalars()}
    assert jobs["1"].still_listed
    assert not jobs["2"].still_listed, "a healthy source no longer lists this"


def test_a_broken_source_does_not_retire_its_postings(session, scorer):
    """Degrade to stale data, never to an empty feed that looks real."""
    run_scan(session, [StubAdapter("a", [job("a", "1")])], scorer)
    run_scan(session, [StubAdapter("a", error=RuntimeError("500"))], scorer)

    stored = session.execute(select(Job)).scalars().one()
    assert stored.still_listed, "a broken scraper is not evidence a job closed"


def test_a_posting_edited_by_the_employer_is_refreshed_not_duplicated(session, scorer):
    run_scan(session, [StubAdapter("a", [job("a", "1", title="Operations Director")])], scorer)
    run_scan(session, [StubAdapter("a", [job("a", "1", title="Operations Director (Riyadh)")])], scorer)

    stored = session.execute(select(Job)).scalars().one()
    assert stored.title == "Operations Director (Riyadh)"
    assert stored.first_seen_at <= stored.last_seen_at


# -- scoring integration -----------------------------------------------------

def test_scores_are_stored_with_a_readable_breakdown(session, scorer):
    run_scan(session, [StubAdapter("a", [job("a", "1")])], scorer)
    stored = session.execute(select(Job)).scalars().one()

    assert stored.score is not None
    assert stored.score.lane == "A"
    assert stored.score.employer_tier == 1
    labels = [entry["label"] for entry in stored.score.breakdown]
    assert any("Riyadh" in label for label in labels)
    assert sum(e["contribution"] for e in stored.score.breakdown) == stored.score.raw_score


def test_an_excluded_posting_is_stored_with_its_reason(session, scorer):
    run_scan(session, [StubAdapter("a", [
        job("a", "1", description="Saudi nationals only.")
    ])], scorer)
    stored = session.execute(select(Job)).scalars().one()

    assert stored.score.excluded
    assert "Saudi nationals" in stored.score.exclusion_reason


# -- warm routes -------------------------------------------------------------

def test_warm_counts_match_a_contact_tagged_to_the_employer(session, scorer):
    session.add(Contact(name="A Person", target_employer="Nesma & Partners"))
    session.add(Contact(name="Another", target_employer="Nesma"))
    session.flush()

    counts = warm_contact_counts(session, [job("a", "1")])
    assert counts[job("a", "1").fingerprint] == 2


def test_warm_route_is_applied_during_a_scan(session, scorer):
    session.add(Contact(name="A Person", target_employer="Nesma & Partners"))
    session.flush()

    run_scan(session, [StubAdapter("a", [job("a", "1")])], scorer)
    stored = session.execute(select(Job)).scalars().one()

    assert stored.score.warm_route
    assert stored.score.warm_contact_count == 1


def test_no_contacts_means_no_warm_routes_invented(session, scorer):
    run_scan(session, [StubAdapter("a", [job("a", "1")])], scorer)
    stored = session.execute(select(Job)).scalars().one()
    assert not stored.score.warm_route
    assert stored.score.warm_contact_count == 0
