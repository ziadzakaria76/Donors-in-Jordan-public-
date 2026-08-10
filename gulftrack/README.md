# GulfTrack

A private job intelligence system for one senior candidate in the Saudi
construction and infrastructure market. It scans sources on a schedule, scores
every opening deterministically, links openings to people already known inside
the hiring employer, pre-fills applications for one-tap human approval, and
exports the pipeline to Word and Excel.

Two rules override everything else in this codebase:

1. **Applications are never submitted automatically.** Every submission passes
   through a human tap. There is no automatic mode and none will be added.
2. **No fabricated records.** If a scan returns nothing, the feed shows zero.
   Sample and placeholder jobs never enter the database.

## State

M1 in progress. Complete and tested: the candidate profile, the scoring engine,
the source-adapter contract. Not yet built: adapters, database persistence, API,
front end.

## Layout

    backend/
      app/adapters/base.py     the contract every source implements
      app/scoring/engine.py    deterministic scoring — no LLM, no network
      app/scoring/profile.py   profile loading and validation
      profiles/                the seed profile; the database is authoritative
      tests/                   fixtures live here and nowhere else

## Running the tests

    cd backend && ../.venv/bin/python -m pytest

## Scoring

Rule-based and reproducible. The same posting scored twice yields the same
number, and every score decomposes into named signals shown on the job card:

    Stadium / sports venue delivery +25, District cooling / energy centre +22,
    Client-Side title match +20, MEP scope +18, ... = 157, capped at 100

Ranking uses the uncapped raw score so jobs that both display as 100 still
order by real strength. Weights are editable from Settings; the YAML is only
the seed.

Language models are used for summaries, drafting and translation — never for
scoring, which must stay auditable and free.

## Adapters

Each source is a self-contained module implementing `fetch() -> list[JobPosting]`.
Adding one never touches the scoring engine, and one failing adapter never
aborts a scan. Every adapter carries a plain-language `repair_note` describing
what it fetches and from where, so a future repair is a ten-minute job.

Sources that prohibit automated access are implemented as `DeepLinkSource`,
which refuses to fetch and generates a pre-filtered search URL instead. Bayt
and LinkedIn are both in this category.
