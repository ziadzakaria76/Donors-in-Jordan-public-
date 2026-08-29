"""Command line.

    --check-portals      reachability only, no parsing
    --dry-run            scrape, filter, print. Sends nothing.
    --run                full run, writes output files. Nothing is delivered:
                         the report is the files, and you download them.
    --capture PORTAL     fetch a portal's live pages, save them, report per-layer
                         row counts, quality, the winning layer, and the
                         structural selectors the page actually uses
    --self-test          run the pipeline over committed fixtures, never touching
                         real state
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from .config import load_config
from .fetch import Fetcher, TransportError
from .models import LINK_TYPES
from .pipeline import run as run_pipeline, scope_summary
from .portals import HTML_PORTALS, REGISTRY
from .report import write_docx, write_json, write_summary, write_xlsx
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
    """Fetch a portal's live pages and report what the cascade makes of them.

    `--capture all` walks every HTML portal, which is how a first pass over the
    whole set gets done in one command -- including from a phone, via the
    workflow, since the report is mirrored into the CI run summary.
    """
    targets = HTML_PORTALS if name == "all" else [name]
    if name != "all" and name not in REGISTRY:
        print(f"unknown portal '{name}'. Known: {', '.join(REGISTRY)}, or 'all'")
        return 2

    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    def say(text: str = "") -> None:
        print(text)
        lines.append(text)

    failures = 0
    for target in targets:
        portal = _build(cfg, target)
        say(f"## {portal.label}  ({portal.url})")
        reason = portal.unavailable_reason()
        if reason:
            # Reported, not obeyed. A run skips such a portal; a capture is how
            # you find out what it needs, so it goes ahead with whatever pages
            # it can reach.
            say(f"  NOTE: {reason}")

        captured = portal.capture()
        if not captured:
            failures += 1
            say(f"  nothing captured: {getattr(portal, '_capture_error', 'no pages defined')}")
            say()
            continue

        for label, html, status, result in captured:
            path = LIVE_DIR / f"{target}-{label}.html"
            path.write_text(html or "", encoding="utf-8")
            say(f"  {label}: HTTP {status}, {len(html or '')} bytes -> {path.name}")
            if result is None:
                continue
            say("    layer results (quality >= 0.45 wins):")
            for attempt in result.attempts:
                note = f"  {attempt.note}" if attempt.note else ""
                say(f"      {attempt.layer:<15} rows={len(attempt.rows):<5} "
                    f"quality={attempt.quality:.2f}{note}")
            say(f"    winner: {result.layer} ({result.quality:.2f})")
            if result.diagnosis:
                failures += 1
                say(f"    diagnosis: {result.diagnosis}")
            for extra in _structure_lines(html):
                say(extra)
            if target == "ungm":
                for extra in _ungm_country_lines(html):
                    say(extra)
        say()

    _write_step_summary("Capture report", lines)
    return 1 if failures else 0


def _write_step_summary(title: str, lines: list[str]) -> None:
    """Mirror a report into the GitHub Actions run page, when running there.

    This is what makes --capture usable without a terminal: the answer is on
    the run summary rather than buried in a log.
    """
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as fh:
        fh.write(f"# {title}\n\n```\n" + "\n".join(lines) + "\n```\n")


def _structure_lines(html: str) -> list[str]:
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
    return ["    repeated selectors on this page: " + ", ".join(common)] if common else []


def _ungm_country_lines(html: str) -> list[str]:
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
        return [f"    {COUNTRY_SELECT_ID} not found on this page -- capture the notice page itself"]
    options = [(o.get("value"), o.get_text(strip=True)) for o in select.find_all("option")]
    out = [f"    {COUNTRY_SELECT_ID}: {len(options)} options"]
    for value, text in options:
        if "syria" in text.lower() or "syrian" in text.lower():
            out.append(f"      >>> set portals.ungm.country_id: {value}    ({text})")
    return out


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
        suffix = f" -- {entry['error']}" if entry.get("error") else ""
        print(f"  {entry['list']}: fetched {entry['fetched']}, {entry['names']} names{suffix}")
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
    parser.add_argument("--capture", metavar="PORTAL",
                        help=f"one of: {', '.join(HTML_PORTALS)}, or 'all' "
                             "(REST portals dump their payload)")
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
    top_n = cfg.get("output.top_n", 10)
    formats = cfg.get("output.formats", ["docx", "xlsx"])
    written = []
    if "docx" in formats:
        written.append(write_docx(result, out_dir / f"syria-tenders-{stamp}.docx", top_n))
    if "xlsx" in formats:
        written.append(write_xlsx(result, out_dir / f"syria-tenders-{stamp}.xlsx"))
    if "json" in formats:
        written.append(write_json(result, out_dir / f"syria-tenders-{stamp}.json", cfg.profile))

    # Always written, whatever the formats: it is what carries portal health to
    # somewhere a person sees without opening a document.
    summary = write_summary(result, out_dir / f"syria-tenders-{stamp}-summary.md", top_n)
    written.append(summary)

    store.record(result.tenders)

    print("\nFiles written to " + str(out_dir.resolve()) + ":")
    for path in written:
        print(f"  {path.name}  ({path.stat().st_size:,} bytes)")

    # In GitHub Actions the summary also goes to the run page, so a scheduled
    # run's health is visible in the run list without downloading anything.
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(summary.read_text(encoding="utf-8") + "\n")
        print("  (summary also appended to the workflow run page)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
