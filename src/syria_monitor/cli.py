"""Command line.

    --check-portals      reachability only, no parsing
    --dry-run            scrape, filter, print. Sends nothing.
    --run                full run, writes output files. Sends nothing without --send.
    --send               deliver by Graph (only meaningful with --run)
    --capture PORTAL     fetch a portal's live pages, save them, report per-layer
                         row counts, quality, the winning layer, and the
                         structural selectors the page actually uses
    --self-test          run the pipeline over committed fixtures, never touching
                         real state
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .config import load_config
from .fetch import Fetcher, TransportError
from .models import LINK_TYPES
from .pipeline import run as run_pipeline, scope_summary
from .portals import HTML_PORTALS, REGISTRY
from .report import render_email, write_docx, write_json, write_xlsx
from .report.common import LINK_LABELS, fmt_date, fmt_value

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
LIVE_DIR = FIXTURE_DIR / "live"


def _build(cfg, name):
    from .classify import Classifier
    from .gate import CountryGate
    from .matching import CountryMatcher
    matcher = CountryMatcher(cfg.profile)
    gate = CountryGate(cfg.profile, matcher, Classifier(cfg.profile, matcher))
    return REGISTRY[name](cfg.portal_cfg(name), cfg.profile, Fetcher(), gate)


def check_portals(cfg) -> int:
    print("Portal reachability\n" + "-" * 60)
    failures = 0
    for name in cfg.enabled_portals:
        portal = _build(cfg, name)
        reason = portal.unavailable_reason()
        if reason:
            print(f"  {portal.label:<26} SKIPPED  {reason}")
            continue
        try:
            response = Fetcher().get(portal.url)
            state = "ok" if response.ok else f"HTTP {response.status}"
            failures += 0 if response.ok else 1
            print(f"  {portal.label:<26} {state:<8} {portal.url}")
        except TransportError as exc:
            failures += 1
            print(f"  {portal.label:<26} FAIL     {exc}  ({portal.url})")
    return 1 if failures else 0


def capture(cfg, name: str) -> int:
    if name not in REGISTRY:
        print(f"unknown portal '{name}'. Known: {', '.join(REGISTRY)}")
        return 2
    portal = _build(cfg, name)
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Capturing {portal.label} -> {LIVE_DIR}")

    captured = portal.capture()
    if not captured:
        print(f"  nothing captured: {getattr(portal, '_capture_error', 'no pages defined')}")
        return 1

    for label, html, status, result in captured:
        path = LIVE_DIR / f"{name}-{label}.html"
        path.write_text(html or "", encoding="utf-8")
        print(f"  {label}: HTTP {status}, {len(html or '')} bytes -> {path}")
        if result is None:
            continue
        print("    layer results (quality >= 0.45 wins):")
        for attempt in result.attempts:
            note = f"  {attempt.note}" if attempt.note else ""
            print(f"      {attempt.layer:<15} rows={len(attempt.rows):<5} "
                  f"quality={attempt.quality:.2f}{note}")
        print(f"    winner: {result.layer} ({result.quality:.2f})")
        if result.diagnosis:
            print(f"    diagnosis: {result.diagnosis}")
        _print_structure(html)
        if name == "ungm":
            _print_ungm_countries(html)
    return 0


def _print_structure(html: str) -> None:
    """Report the selectors the page actually uses, derived structurally."""
    from bs4 import BeautifulSoup
    from collections import Counter
    soup = BeautifulSoup(html or "", "html.parser")
    counter: Counter = Counter()
    for element in soup.find_all(True):
        classes = element.get("class") or []
        for cls in classes:
            counter[f"{element.name}.{cls}"] += 1
    common = [f"{sel} x{n}" for sel, n in counter.most_common(12) if n >= 3]
    if common:
        print("    repeated selectors on this page: " + ", ".join(common))


def _print_ungm_countries(html: str) -> None:
    """Read the numeric country ids out of the live dropdown.

    UNGM uses its own ids, not ISO codes, and there is no table to derive one
    from -- this is the only way to learn the right value for config.yml.
    """
    from bs4 import BeautifulSoup
    from .portals.ungm import COUNTRY_SELECT_ID
    soup = BeautifulSoup(html or "", "html.parser")
    select = soup.find("select", id=COUNTRY_SELECT_ID) or soup.find("select",
                                                                    attrs={"name": COUNTRY_SELECT_ID})
    if not select:
        print(f"    {COUNTRY_SELECT_ID} not found on this page -- capture the notice page itself")
        return
    options = [(o.get("value"), o.get_text(strip=True)) for o in select.find_all("option")]
    print(f"    {COUNTRY_SELECT_ID}: {len(options)} options")
    for value, text in options:
        if "syria" in text.lower() or "syrian" in text.lower():
            print(f"      >>> set portals.ungm.country_id: {value}    ({text})")


def _print_result(result, cfg) -> None:
    print("\n" + result.subject())
    print("-" * 78)
    for portal in result.portals:
        print("  " + portal.status_line)
    print("-" * 78)
    print(scope_summary(result))
    for key in LINK_TYPES:
        print(f"  {LINK_LABELS.get(key, key):<32} {result.counts.get(key, 0)}")
    print(f"  duplicates collapsed: {result.duplicates_collapsed} | "
          f"expired dropped: {result.expired_dropped}")
    if result.screening_error:
        print(f"  SCREENING ERROR: {result.screening_error}")
    for entry in result.screening_status:
        print(f"  {entry['list']}: fetched {entry['fetched']}, {entry['names']} names")
    print("-" * 78)
    for rank, tender in enumerate(result.tenders[:cfg.get("output.top_n", 10)], start=1):
        flag = "NEW " if tender.is_new else "    "
        print(f"{rank:>3}. {flag}[{tender.score:5.1f}] {tender.title[:64]}")
        print(f"         {tender.portal} | closes {fmt_date(tender.closing_date)} | "
              f"{fmt_value(tender)} | {tender.syria_link_type}")
    if not result.tenders:
        print("  (nothing in scope -- check portal health above before concluding it was quiet)")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="syria-monitor")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--check-portals", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--send", action="store_true",
                        help="deliver by Graph; without it a run only writes files")
    parser.add_argument("--capture", metavar="PORTAL",
                        help=f"one of: {', '.join(HTML_PORTALS)} (REST portals dump their payload)")
    parser.add_argument("--self-test", action="store_true",
                        help="pipeline over committed fixtures; never touches real state")
    parser.add_argument("--portal", action="append",
                        help="limit the run to these portals (repeatable)")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)

    if args.check_portals:
        return check_portals(cfg)
    if args.capture:
        return capture(cfg, args.capture)
    if args.self_test:
        from .selftest import self_test
        return self_test(cfg)
    if not (args.dry_run or args.run):
        parser.print_help()
        return 0

    from .screening import Screener
    from .state import SeenStore

    screener = None
    if cfg.get("screening.enabled", True):
        screener = Screener(Path(cfg.get("screening.cache_dir", ".cache/sanctions")),
                            fetcher=Fetcher(), max_age_days=cfg.get("screening.max_age_days", 7))
    store = SeenStore(cfg.db_path, read_only=args.dry_run)

    result = run_pipeline(cfg, screener=screener, store=store, portals=args.portal)
    _print_result(result, cfg)

    if args.dry_run:
        print("\nDRY RUN -- nothing written, nothing sent, seen-database untouched.")
        return 0

    out_dir = cfg.output_dir
    stamp = date.today().isoformat()
    written = []
    formats = cfg.get("output.formats", ["docx", "xlsx", "json"])
    if "docx" in formats:
        written.append(write_docx(result, out_dir / f"syria-tenders-{stamp}.docx",
                                  cfg.get("output.top_n", 10)))
    if "xlsx" in formats:
        written.append(write_xlsx(result, out_dir / f"syria-tenders-{stamp}.xlsx"))
    if "json" in formats:
        written.append(write_json(result, out_dir / f"syria-tenders-{stamp}.json", cfg.profile))
    print("\nWrote:")
    for path in written:
        print(f"  {path}")

    store.record(result.tenders)

    if not args.send:
        print("\nNot sent. Review the files above, then re-run with --send to deliver.")
        return 0

    from .delivery import GraphMailer, MailError, recipients_from_env
    to, cc = recipients_from_env()
    try:
        notes = GraphMailer().send(result.subject(), render_email(result, cfg.get("output.top_n", 10)),
                                   to, cc, written)
        print(f"\nSent to {len(to)} recipient(s)." + ("" if not notes else f" {notes}"))
    except MailError as exc:
        print(f"\nDELIVERY FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
