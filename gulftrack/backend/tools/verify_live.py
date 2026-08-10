"""Run the real scan against a live source and print what it found.

This is the check that decides whether an adapter is allowed into the default
scan. Passing tests is not the bar — the bar is a successful run against the
live site with the field mapping visibly correct.

Runs against a throwaway in-memory database. Writes nothing that survives the
job, and submits nothing anywhere.

    python tools/verify_live.py
    python tools/verify_live.py --max-descriptions 40
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.adapters.http import PoliteClient  # noqa: E402
from app.adapters.workable import (  # noqa: E402
    API_DELAY_SECONDS, KNOWN_BOARDS, WorkableAdapter,
)
from app.models import Base, Job, JobScore  # noqa: E402
from app.scan import run_scan  # noqa: E402
from app.scoring.engine import ScoringEngine  # noqa: E402
from app.scoring.profile import load_profile  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-descriptions", type=int, default=60,
                        help="cap per-job description fetches to keep CI short")
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    client = PoliteClient(delay_seconds=API_DELAY_SECONDS)
    adapters = [
        WorkableAdapter(board, client, max_descriptions=args.max_descriptions)
        for board in KNOWN_BOARDS
    ]

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    scorer = ScoringEngine(load_profile())

    print("## Live scan\n")
    with Session(engine) as session:
        summary = run_scan(session, adapters, scorer, holder="verify_live")
        session.commit()

        print(f"**{summary.describe()}**\n")
        print(f"Status: `{summary.status.value}`")
        if summary.failed_sources:
            print(f"Failed sources: {', '.join(summary.failed_sources)}")
        print(f"\nDescription fetches capped at {args.max_descriptions}; "
              f"postings beyond that are scored on title, location and "
              f"department only, so their scores understate the real fit.\n")

        rows = session.execute(
            select(Job).join(JobScore, JobScore.fingerprint == Job.fingerprint)
            .order_by(JobScore.raw_score.desc())
        ).scalars().unique().all()

        visible = [j for j in rows if not j.score.excluded and not j.score.suppressed]
        hidden = [j for j in rows if j.score.excluded or j.score.suppressed]

        print(f"### Top {min(args.top, len(visible))} of {len(visible)} visible matches\n")
        for job in visible[: args.top]:
            score = job.score
            breakdown = ", ".join(
                f"{c['label']} {'+' if c['contribution'] >= 0 else '−'}"
                f"{abs(c['contribution'])}"
                for c in score.breakdown
            ) or "no signals fired"
            print(f"**{score.score}** — {job.title}")
            print(f"  {job.employer} · {job.location or 'location not stated'}"
                  f" · lane {score.lane or '—'} · tier {score.employer_tier or '—'}")
            print(f"  {breakdown} = {score.raw_score}")
            print(f"  {job.url}\n")

        if hidden:
            print(f"### {len(hidden)} hidden\n")
            for job in hidden[:10]:
                reason = (job.score.exclusion_reason
                          or job.score.suppression_reason or "unknown")
                print(f"- {job.title} — {reason}")

        # The scoring engine's own guarantee, checked against live data rather
        # than fixtures: every score must reconcile with its breakdown.
        mismatched = [
            j for j in rows
            if sum(c["contribution"] for c in j.score.breakdown) != j.score.raw_score
        ]
        print(f"\nBreakdowns reconciling with their score: "
              f"{len(rows) - len(mismatched)}/{len(rows)}")
        if mismatched:
            print("**A score did not reconcile with its breakdown.**")
            return 1

        if not rows:
            print("\n**No postings returned. The adapter is not working.**")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
