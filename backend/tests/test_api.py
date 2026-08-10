"""API and feed page.

Every posting here is a fixture created inside the test. The point of several
of these tests is that the app shows an honest zero rather than filling space.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.base import AccessMode, JobPosting, SourceTier
from app.db import get_session
from app.main import app
from app.models import Base, Contact
from app.scan import run_scan
from app.scoring.engine import ScoringEngine
from app.scoring.profile import load_profile


@pytest.fixture
def db():
    # StaticPool keeps every connection on the same in-memory database. Without
    # it, the request thread opens a second connection, gets its own empty
    # database, and every query fails on a missing table.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def client(db, tmp_path, monkeypatch):
    # The app's lifespan calls init_db() against the configured database. Point
    # it at a throwaway file so a test run never touches a real one.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'lifespan.db'}")
    monkeypatch.setattr("app.db._engine", None, raising=False)
    monkeypatch.setattr("app.db._Session", None, raising=False)

    def override():
        session = db()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def scorer():
    return ScoringEngine(load_profile())


class StubAdapter:
    tier = SourceTier.STRUCTURED
    access_mode = AccessMode.FETCH
    repair_note = "stub"

    def __init__(self, source_id, postings=None, error=None):
        self.source_id = source_id
        self.display_name = source_id
        self._postings = postings or []
        self._error = error

    def fetch(self):
        if self._error:
            raise self._error
        return list(self._postings)


def job(jid="1", **kw):
    base = dict(
        source_id="src",
        source_job_id=jid,
        title="Stadium Delivery Director",
        employer="Qiddiya Investment Company",
        url=f"https://example.com/{jid}",
        location="Riyadh",
        description="District cooling energy centre and MEP delivery.",
    )
    base.update(kw)
    return JobPosting(**base)


def seed(db, scorer, adapters):
    session = db()
    try:
        summary = run_scan(session, adapters, scorer)
        session.commit()
        return summary
    finally:
        session.close()


# -- honest empty states -----------------------------------------------------

def test_an_empty_system_reports_zero_and_says_why(client):
    body = client.get("/api/matches").json()
    assert body["count"] == 0
    assert body["matches"] == []

    page = client.get("/")
    assert page.status_code == 200
    assert "No matches" in page.text
    assert "No sources are being scanned yet" in page.text


def test_the_page_never_invents_a_row(client, db, scorer):
    seed(db, scorer, [StubAdapter("src", error=RuntimeError("portal down"))])
    page = client.get("/")
    assert "No matches" in page.text
    assert "example.com" not in page.text


# -- the feed ----------------------------------------------------------------

def test_a_scanned_job_appears_with_its_breakdown(client, db, scorer):
    seed(db, scorer, [StubAdapter("src", [job()])])

    body = client.get("/api/matches").json()
    assert body["count"] == 1
    match = body["matches"][0]
    assert match["employer"] == "Qiddiya Investment Company"
    assert match["lane"] == "B"
    assert match["url"].startswith("https://")
    assert sum(c["contribution"] for c in match["breakdown"]) == match["raw_score"]

    page = client.get("/")
    assert "Stadium Delivery Director" in page.text
    assert "District cooling" in page.text
    assert 'href="https://example.com/1"' in page.text


def test_excluded_and_suppressed_jobs_are_hidden_but_retrievable(client, db, scorer):
    seed(db, scorer, [StubAdapter("src", [
        job("1"),
        job("2", title="Operations Director", description="Saudi nationals only."),
    ])])

    visible = client.get("/api/matches").json()
    assert visible["count"] == 1

    everything = client.get("/api/matches", params={"include_hidden": True}).json()
    assert everything["count"] == 2
    hidden = [m for m in everything["matches"] if m["excluded"]][0]
    assert "Saudi nationals" in hidden["exclusion_reason"]


def test_lane_and_score_filters_apply(client, db, scorer):
    seed(db, scorer, [StubAdapter("src", [
        job("1"),
        job("2", title="Operations Director", employer="Nesma & Partners",
            description="Design and build portfolio."),
    ])])

    assert client.get("/api/matches", params={"lane": "A"}).json()["count"] == 1
    assert client.get("/api/matches", params={"lane": "B"}).json()["count"] == 1
    assert client.get("/api/matches", params={"min_score": 95}).json()["count"] == 1


def test_a_warm_route_is_shown_on_the_card(client, db, scorer):
    session = db()
    session.add(Contact(name="A Person", target_employer="Qiddiya"))
    session.commit()
    session.close()

    seed(db, scorer, [StubAdapter("src", [job()])])
    page = client.get("/")
    assert "Warm route — 1 contact" in page.text


def test_job_detail_404s_rather_than_inventing_one(client):
    assert client.get("/api/jobs/does-not-exist").status_code == 404


# -- system honesty ----------------------------------------------------------

def test_a_broken_source_is_surfaced_on_the_home_screen(client, db, scorer):
    for _ in range(3):
        seed(db, scorer, [StubAdapter("src", error=RuntimeError("timeout"))])

    status = client.get("/api/status").json()
    assert status["sources_broken"] == 1
    assert any("broken" in w for w in status["warnings"])

    page = client.get("/")
    assert "Needs attention" in page.text
    assert "broken" in page.text


def test_a_skipped_scan_is_surfaced_not_swallowed(client, db, scorer):
    from app.models import ScanLock, utcnow

    seed(db, scorer, [StubAdapter("src", [job()])])
    session = db()
    session.add(ScanLock(id=1, scan_run_id=999, acquired_at=utcnow()))
    session.commit()
    session.close()

    seed(db, scorer, [StubAdapter("src", [job("2")])])

    status = client.get("/api/status").json()
    assert status["last_scan"]["status"] == "skipped"
    assert any("skipped" in w for w in status["warnings"])


def test_source_health_exposes_the_repair_note(client, db, scorer):
    seed(db, scorer, [StubAdapter("src", [job()])])
    sources = client.get("/api/sources").json()["sources"]
    assert sources[0]["repair_note"] == "stub"
    assert sources[0]["last_posting_count"] == 1
    assert not sources[0]["broken"]


# -- deep links --------------------------------------------------------------

def test_deep_links_carry_their_terms_basis_and_verification_state(client):
    links = client.get("/api/deep-links", params={"query": "Operations Director"}).json()["links"]
    by_id = {link["source_id"]: link for link in links}

    assert "Operations+Director" in by_id["bayt"]["url"]
    assert "saved searches" in by_id["bayt"]["why_not_scraped"]
    assert "prohibits automated access" in by_id["linkedin"]["why_not_scraped"]
    # Not yet opened against the live site, and the API says so.
    assert all(not link["verified"] for link in links)


def test_deep_link_sources_refuse_to_fetch():
    from app.adapters.registry import deep_link_sources

    for source in deep_link_sources():
        with pytest.raises(NotImplementedError):
            source.fetch()
