"""API and the M1 match feed.

The page served here is deliberately plain — the real interface arrives at M2.
What it must already do is tell the truth: show the scan's actual state, name
any broken source on the home screen, and show zero when there is nothing,
rather than filling the page to look busy.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.adapters.registry import DEEP_LINK_SPECS, deep_link_sources
from app.db import get_session, init_db
from app.models import Job, JobScore, ScanRun, ScanStatus, Source

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="GulfTrack", lifespan=lifespan)


# --------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------

def feed_query(
    lane: str | None = None,
    min_score: int = 0,
    include_hidden: bool = False,
):
    """The match feed.

    Ordered by raw score so jobs that both display as 100 keep their real
    ordering, with warm routes breaking ties — the 'above equivalently-scored
    cold opportunities' rule from section 8.
    """
    stmt = (
        select(Job)
        .join(JobScore, JobScore.fingerprint == Job.fingerprint)
        .options(joinedload(Job.score))
    )
    if not include_hidden:
        stmt = stmt.where(
            JobScore.excluded.is_(False),
            JobScore.suppressed.is_(False),
            Job.still_listed.is_(True),
        )
    if lane:
        stmt = stmt.where(JobScore.lane == lane)
    if min_score:
        stmt = stmt.where(JobScore.score >= min_score)
    return stmt.order_by(
        desc(JobScore.raw_score), desc(JobScore.warm_route), Job.employer
    )


def _serialise(job: Job) -> dict:
    score = job.score
    return {
        "fingerprint": job.fingerprint,
        "title": job.title,
        "employer": job.employer,
        "location": job.location,
        "url": job.url,
        "source_id": job.source_id,
        "posted_date": job.posted_date,
        "closing_date": job.closing_date,
        "salary_raw": job.salary_raw,
        "language": job.language,
        "first_seen_at": job.first_seen_at,
        "still_listed": job.still_listed,
        "score": score.score if score else None,
        "raw_score": score.raw_score if score else None,
        "band": score.band if score else None,
        "lane": score.lane if score else None,
        "employer_tier": score.employer_tier if score else None,
        "breakdown": score.breakdown if score else [],
        "flags": score.flags if score else [],
        "warm_route": score.warm_route if score else False,
        "warm_contact_count": score.warm_contact_count if score else 0,
        "excluded": score.excluded if score else False,
        "exclusion_reason": score.exclusion_reason if score else None,
        "suppressed": score.suppressed if score else False,
        "suppression_reason": score.suppression_reason if score else None,
    }


def system_status(session: Session) -> dict:
    """What the home screen needs to be honest about the system's condition."""
    latest = session.execute(
        select(ScanRun).order_by(desc(ScanRun.started_at)).limit(1)
    ).scalars().first()

    sources = session.execute(select(Source)).scalars().all()
    broken = [s for s in sources if s.broken]
    degraded = [s for s in sources if s.consecutive_failures and not s.broken]

    fetch_sources = [s for s in sources if s.access_mode.value == "fetch"]
    healthy = [s for s in fetch_sources if not s.consecutive_failures]

    warnings: list[str] = []
    if broken:
        names = ", ".join(s.display_name for s in broken)
        warnings.append(
            f"{len(broken)} source{'s' if len(broken) != 1 else ''} broken: {names}. "
            "Their last known jobs are still shown and marked stale."
        )
    if degraded:
        warnings.append(
            f"{len(degraded)} source{'s' if len(degraded) != 1 else ''} failed "
            "on the last scan but has not yet been marked broken."
        )
    if latest is None:
        warnings.append("No scan has run yet.")
    elif latest.status is ScanStatus.SKIPPED:
        warnings.append(
            "The last scheduled scan was skipped because the previous one was "
            "still running."
        )
    elif latest.status is ScanStatus.FAILED:
        warnings.append("The last scan failed. No source returned anything.")
    if not fetch_sources:
        warnings.append(
            "No fetch sources are configured yet, so nothing is being scanned. "
            "Deep-link portals below are opened by hand."
        )

    return {
        "last_scan": {
            "id": latest.id,
            "status": latest.status.value,
            "started_at": latest.started_at,
            "finished_at": latest.finished_at,
            "postings_seen": latest.postings_seen,
            "postings_new": latest.postings_new,
            "sources_attempted": latest.sources_attempted,
            "sources_failed": latest.sources_failed,
            "note": latest.note,
        } if latest else None,
        "sources_total": len(fetch_sources),
        "sources_healthy": len(healthy),
        "sources_broken": len(broken),
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# JSON API
# --------------------------------------------------------------------------

@app.get("/api/status")
def read_status(session: SessionDep) -> dict:
    return system_status(session)


@app.get("/api/matches")
def read_matches(
    session: SessionDep,
    lane: Annotated[str | None, Query(pattern="^[AB]$")] = None,
    min_score: Annotated[int, Query(ge=0, le=100)] = 0,
    include_hidden: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict:
    jobs = session.execute(
        feed_query(lane, min_score, include_hidden).limit(limit)
    ).scalars().unique().all()
    return {"count": len(jobs), "matches": [_serialise(j) for j in jobs]}


@app.get("/api/jobs/{fingerprint}")
def read_job(fingerprint: str, session: SessionDep) -> dict:
    job = session.get(Job, fingerprint)
    if job is None:
        raise HTTPException(status_code=404, detail="No such job")
    return _serialise(job)


@app.get("/api/sources")
def read_sources(session: SessionDep) -> dict:
    rows = session.execute(select(Source).order_by(Source.id)).scalars().all()
    return {
        "sources": [
            {
                "id": s.id,
                "display_name": s.display_name,
                "tier": s.tier,
                "access_mode": s.access_mode.value,
                "enabled": s.enabled,
                "broken": s.broken,
                "consecutive_failures": s.consecutive_failures,
                "last_success_at": s.last_success_at,
                "last_attempt_at": s.last_attempt_at,
                "last_error": s.last_error,
                "last_posting_count": s.last_posting_count,
                "repair_note": s.repair_note,
            }
            for s in rows
        ]
    }


@app.get("/api/deep-links")
def read_deep_links(
    query: Annotated[str, Query(min_length=2, max_length=120)] = "Operations Director",
    location: str = "Saudi Arabia",
) -> dict:
    """Pre-filtered searches on portals we are not permitted to scrape."""
    verified = {spec.source_id: spec.verified for spec in DEEP_LINK_SPECS}
    return {
        "links": [
            {
                "source_id": s.source_id,
                "display_name": s.display_name,
                "url": s.search_url(query, location),
                "why_not_scraped": s.tos_basis,
                # Honesty flag: the template was written from the portal's
                # documented URL shape but has not yet been opened live.
                "verified": verified.get(s.source_id, False),
            }
            for s in deep_link_sources()
        ]
    }


# --------------------------------------------------------------------------
# The M1 page
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def feed_page(
    request: Request,
    session: SessionDep,
    lane: Annotated[str | None, Query(pattern="^[AB]$")] = None,
    min_score: Annotated[int, Query(ge=0, le=100)] = 0,
) -> HTMLResponse:
    jobs = session.execute(
        feed_query(lane, min_score).limit(200)
    ).scalars().unique().all()
    return TEMPLATES.TemplateResponse(
        request,
        "feed.html",
        {
            "matches": [_serialise(j) for j in jobs],
            "status": system_status(session),
            "lane": lane,
            "min_score": min_score,
            "generated_at": datetime.now(timezone.utc),
        },
    )
