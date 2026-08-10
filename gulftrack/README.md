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

M1 complete. Scoring engine, candidate profile, database, scan runner with an
overlap lock, source-health tracking, API, match feed, polite HTTP client, and
one live source.

Live source: Qiddiya Investment Company, via its Workable board. Verified
10 August 2026 — a real scan returned all 278 postings, every score
reconciling with its breakdown.

Not built yet: CV handling (M3), exports (M4), Assisted Apply (M5), the full
network module (M6), push notifications and PWA packaging (M7).

### Employers investigated, and what runs their careers pages

| Employer | Platform | Status |
| --- | --- | --- |
| Qiddiya | Workable | **Live.** Their own site is bot-protected; the board is not |
| Diriyah | SAP SuccessFactors (`thediriyah`) | Serves HTML, not the RSS asked for |
| ROSHN | Oracle Recruiting | API behind a WAF — deep-link only |
| Nesma & Partners | SAP SuccessFactors | Not yet attempted |
| Johnson Controls | Workday (`jci`, site `JCI`) | Endpoint works; query returns nothing yet |
| SEVEN, Soudah, DGDA | — | Bot challenge. Deep-link candidates |
| Others | — | Unidentified, unreachable, or no careers page found |

Reconnaissance runs from GitHub Actions, because the development environment
cannot reach any of these hosts. See `tools/recon.py`.

### The bar for an adapter

Passing tests is not the bar. An adapter joins the scan only after a successful
run against the live site with its field mapping checked in the output, via
`tools/verify_live.py`. Two adapters have failed that bar after passing their
tests: Oracle on a WAF block, and Workable on a 400 caused by one request field
the unit tests happily accepted.

No attempt is made to defeat bot protection. Employers that challenge an
honest, rate-limited, identified client become deep-link sources instead.

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
