#!/usr/bin/env python3
"""Job scanner: read every reachable careers source, score against the frozen
profile, and write the run out in a form that says what it could not do.

    python scanner.py --only kfshrc,jhah --out runs/baseline.xlsx
    python scanner.py --out runs/jobs.xlsx --docx runs/shortlist.docx \
                      --json runs/scan.json --html site/index.html

The module-level note() is the sanctioned channel for non-fatal observations.
It attaches the message to the source's run record, so it lands in the Run
status sheet next to the numbers it explains. Printing to stderr instead
loses it: the weekly run is unattended and nobody reads its console.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jobscan import adapters, config as config_module, normalize, writers  # noqa: E402
from jobscan.adapters import AdapterError  # noqa: E402
from jobscan.fetch import Fetcher  # noqa: E402
from jobscan.run import RunLog  # noqa: E402
from jobscan.scoring import Scorer  # noqa: E402

# The active run, so note() can be called as the brief specifies -- with a
# source key and a message, from anywhere, without threading a log object
# through every call site.
_ACTIVE_RUN: RunLog | None = None


def note(source_key: str, message: str) -> None:
    """Record a non-fatal observation against a source.

    Reaches the Run status sheet. Never use stderr for this.
    """
    global _ACTIVE_RUN
    if _ACTIVE_RUN is None:
        _ACTIVE_RUN = RunLog()
    _ACTIVE_RUN.note(source_key, message)


# Reading these apart matters for what you do next. A gateway refusal is not
# the employer's doing and no amount of reconfiguring the adapter will fix it;
# a login wall means the vacancies are behind a session; a missing endpoint
# means discovery has not been run yet. Lumping all three under "error" sends
# the next person to debug the wrong layer.
_BLOCKED_MARKERS = (
    "proxy refused",
    "connect_rejected",
    "tunnel connection failed",
    "403 to connect",
    "connection failed",
)
_AUTH_MARKERS = ("http 401", "http 403", "sign in", "log in", "login", "authentication")


def _classify(error: str) -> str:
    low = error.lower()
    if any(marker in low for marker in _BLOCKED_MARKERS):
        return "blocked"
    return "error"


def _scan_source(source: dict, fetcher: Fetcher, run_log: RunLog) -> list:
    key = source["key"]
    record = run_log.record(
        key,
        name=source.get("name", ""),
        platform=source.get("platform", ""),
        verified=source.get("verified", "unconfirmed"),
        endpoint=(source.get("api") or {}).get("url") or source.get("careers_url") or "",
    )

    if source.get("permanently_disabled"):
        record.status = "skipped"
        record.note(
            "permanently disabled in sources.yaml; not attempted. "
            + str(source.get("note", "")).strip()
        )
        return []

    if source.get("platform") in (None, "", "unknown"):
        record.status = "skipped"
        record.note(
            "platform is unknown -- the search endpoint has not been discovered yet. "
            "Run discover_playwright.py against the careers URL."
        )
        return []

    if source.get("platform") == "imap":
        record.status = "skipped"
        record.note("IMAP source; credentials are not configured. See SUBSCRIPTIONS.md.")
        return []

    started = time.monotonic()
    try:
        adapter = adapters.get(source["platform"])
        postings = adapter(source, fetcher, record.note)
    except AdapterError as exc:
        record.status = _classify(str(exc))
        record.error = str(exc)
        if record.status == "blocked":
            record.note(
                "refused before the request reached the site -- this is a network or "
                "egress-policy block, not an employer-side failure. Re-run from a "
                "network that can reach the host."
            )
        elif any(marker in str(exc).lower() for marker in _AUTH_MARKERS):
            record.note(
                "the response looks like an authentication wall: these vacancies need a "
                "login or an established session, which is a different problem from "
                "needing a different capture approach"
            )
        record.duration_ms = int((time.monotonic() - started) * 1000)
        return []
    except Exception as exc:  # an adapter bug must not end the run
        record.status = "error"
        record.error = f"unexpected {type(exc).__name__}: {exc}"
        record.duration_ms = int((time.monotonic() - started) * 1000)
        return []

    record.duration_ms = int((time.monotonic() - started) * 1000)
    record.fetched = len(postings)
    record.status = "ok" if postings else "empty"
    return postings


def scan(cfg, only=None, delay=None):
    """Run the scan. Returns (postings, run_log, stats)."""
    global _ACTIVE_RUN
    run_log = _ACTIVE_RUN if _ACTIVE_RUN is not None else RunLog()
    _ACTIVE_RUN = run_log

    fetcher = Fetcher(delay=delay) if delay is not None else Fetcher()
    scorer = Scorer(cfg.profile)

    selected = cfg.select(only)
    selected_keys = {s["key"] for s in selected}

    # Account for every configured source, not just the ones attempted. A
    # source that is silently absent from Run status is indistinguishable from
    # one that was checked and found empty -- and "why is this employer not in
    # the report?" is the first question the sheet should answer.
    for source in cfg.sources:
        if source["key"] in selected_keys:
            continue
        record = run_log.record(
            source["key"],
            name=source.get("name", ""),
            platform=source.get("platform", ""),
            verified=source.get("verified", "unconfirmed"),
            endpoint=source.get("careers_url") or "",
            status="skipped",
        )
        if source.get("permanently_disabled"):
            record.note("permanently disabled; not attempted")
        elif not source.get("enabled"):
            record.note("disabled in sources.yaml; not attempted")
        else:
            record.note("not selected by --only")
        reason = str(source.get("note", "")).strip()
        if reason:
            record.note(reason)

    if not selected:
        note(
            "__run__",
            "no sources were attempted: every source in sources.yaml is disabled and no "
            "--only was given. This is a configuration state, not an employer with no "
            "vacancies.",
        )

    collected: list = []
    per_source: dict[str, list] = {}
    for source in selected:
        found = _scan_source(source, fetcher, run_log)
        per_source[source["key"]] = found
        collected.extend(found)

    unique = normalize.dedupe(collected)
    if len(unique) < len(collected):
        note("__run__", f"dedupe removed {len(collected) - len(unique)} repeated posting(s)")

    kept, dropped, unknown_dates = normalize.keep_recent(unique, cfg.max_age_days)
    if dropped:
        note(
            "__run__",
            f"{len(dropped)} posting(s) dropped as older than max_age_days="
            f"{cfg.max_age_days}",
        )
    if unknown_dates:
        note(
            "__run__",
            f"{unknown_dates} posting(s) kept with no published posting date; their age "
            "is unknown, not fresh",
        )

    scored = scorer.score_all(kept)

    # kept-per-source, counted after dedupe and age filtering.
    for key, found in per_source.items():
        identities = {p.identity for p in found}
        run_log.get(key).kept = sum(1 for p in scored if p.identity in identities)

    stats = {"dropped_stale": len(dropped), "unknown_dates": unknown_dates}
    return scored, run_log, stats


def _report(run_log, postings) -> None:
    totals = run_log.totals()
    width = max((len(r.source_key) for r in run_log.records), default=6)
    print(f"\n{'source'.ljust(width)}  {'status':<8} {'fetched':>7} {'kept':>5}  detail")
    print("-" * (width + 70))
    for record in run_log.records:
        detail = record.error or " | ".join(record.notes) or ""
        print(
            f"{record.source_key.ljust(width)}  {record.status:<8} {record.fetched:>7} "
            f"{record.kept:>5}  {detail[:110]}"
        )
    print(
        f"\n{totals['sources']} source(s) in report · {totals['attempted']} attempted · "
        f"{totals['ok']} ok · {totals['empty']} empty · {totals['error']} error · "
        f"{totals['blocked']} blocked · {totals['skipped']} skipped"
    )
    print(
        f"{len(postings)} posting(s) scored · "
        f"{sum(1 for p in postings if p.shortlisted)} shortlisted"
    )


def main(argv=None) -> int:
    today = _dt.date.today().isoformat()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="path to sources.yaml")
    parser.add_argument("--only", default=None, help="comma-separated source keys")
    parser.add_argument("--out", default=f"runs/jobs_{today}.xlsx", help="xlsx path")
    parser.add_argument("--docx", default=None, help="shortlist .docx path")
    parser.add_argument("--json", dest="json_path", default=None, help="json dump path")
    parser.add_argument("--html", default=None, help="static html page path")
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="seconds between requests (floor of 1.5s is enforced and cannot be lowered)",
    )
    args = parser.parse_args(argv)

    try:
        cfg = config_module.load(args.config)
    except config_module.ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    only = args.only.split(",") if args.only else None
    try:
        postings, run_log, stats = scan(cfg, only=only, delay=args.delay)
    except (ValueError, config_module.ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    written = [
        writers.write_xlsx(
            args.out, postings, run_log, cfg,
            dropped_stale=stats["dropped_stale"], unknown_dates=stats["unknown_dates"],
        )
    ]
    if args.docx:
        written.append(writers.write_docx(args.docx, postings, run_log, cfg))
    if args.json_path:
        written.append(writers.write_json(args.json_path, postings, run_log, cfg))
    if args.html:
        written.append(writers.write_html(args.html, postings, run_log, cfg))

    _report(run_log, postings)
    print()
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
