#!/usr/bin/env python3
"""
Jordan Tender Intelligence Monitor -- orchestrator.

  python run.py                 scrape, build the report, email it
  python run.py --dry-run       scrape and print results, send nothing
  python run.py --save-only     build and save files, send no email
  python run.py --schedule      run continuously on the configured schedule
  python run.py --reset-db      forget every previously reported tender
  python run.py --cron          print cron / Task Scheduler / schedule.py setup
  python run.py --check-portals reachability test only
  python run.py --self-test     run the pipeline against built-in fixtures
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BASE_DIR / ".env")

import config  # noqa: E402

config.refresh_credentials()

import portals  # noqa: E402
from agents import emailer, filter as filter_agent, reporter, scraper, tracker  # noqa: E402

try:
    from colorama import Fore, Style, init as colorama_init

    colorama_init()
    GREEN, RED, YELLOW, CYAN, BOLD, RESET = (
        Fore.GREEN, Fore.RED, Fore.YELLOW, Fore.CYAN, Style.BRIGHT, Style.RESET_ALL
    )
except ImportError:  # pragma: no cover
    GREEN = RED = YELLOW = CYAN = BOLD = RESET = ""


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s",
        handlers=[
            logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("msal").setLevel(logging.WARNING)


log = logging.getLogger("run")


# --------------------------------------------------------------------------
# Terminal helpers
# --------------------------------------------------------------------------
def banner(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 78}\n{text}\n{'=' * 78}{RESET}")


def print_portal_table(statuses: list[dict]) -> None:
    print(f"\n{BOLD}Portal status{RESET}")
    print(f"  {'':2} {'Portal':<30} {'Notices':>8} {'Time':>7}  Detail")
    for status in statuses:
        mark = f"{GREEN}OK{RESET}" if status["ok"] else f"{RED}XX{RESET}"
        detail = "" if status["ok"] else f"{RED}{(status['error'] or '')[:70]}{RESET}"
        print(
            f"  {mark} {status['name']:<30} {status['count']:>8} "
            f"{status['seconds']:>6.1f}s  {detail}"
        )


def print_tender_table(tenders: list[dict], limit: int = 5) -> None:
    if not tenders:
        print(f"\n{YELLOW}No tenders passed the filters.{RESET}")
        return
    print(f"\n{BOLD}Top {min(limit, len(tenders))} results{RESET}")
    print(f"  {'#':<3} {'Score':>5}  {'Portal':<24} {'Deadline':<12} Title")
    print(f"  {'-' * 100}")
    for tender in tenders[:limit]:
        title = (tender.get("title") or "")[:52]
        deadline = tender.get("closing_date") or "n/a"
        colour = (
            GREEN if tender["score"] >= 70
            else YELLOW if tender["score"] >= 40
            else RED
        )
        print(
            f"  {tender['rank']:<3} {colour}{tender['score']:>5.1f}{RESET}  "
            f"{tender['portal'][:24]:<24} {deadline:<12} {title}"
        )


def check_sam_key() -> None:
    if not config.SAM_API_KEY:
        print(f"\n{YELLOW}SAM.gov API key not set.{RESET}")
        print("  Register free at https://sam.gov -> create a login.gov account ->")
        print("  sign in -> Account Details -> Request Public API Key.")
        print("  Approval typically takes 1-4 weeks. Then add SAM_API_KEY to .env.")
        print("  Continuing without SAM.gov.\n")


# --------------------------------------------------------------------------
# Reachability
# --------------------------------------------------------------------------
PROBE_URLS = {
    "worldbank": "https://search.worldbank.org/api/v2/procnotices?rows=1&format=json",
    "ted": "https://api.ted.europa.eu/v3/notices/search",
    "samgov": "https://api.sam.gov/prod/opportunities/v2/search",
    "ebrd": "https://www.ebrd.com/work-with-us/procurement.html",
    "eib": "https://www.eib.org/en/projects/procurement/index.htm",
    "ungm": "https://www.ungm.org/Public/Notice",
    "giz": "https://www.giz.de/en/mediacenter/117.html",
    "kfw": "https://www.kfw-entwicklungsbank.de/International-financing/KfW-Development-Bank/",
    "isdb": "https://www.isdb.org/procurement",
    "fcdo": "https://www.find-tender.service.gov.uk/Search/Results",
    "sfd": "https://www.sfd.gov.sa/en/tenders",
    "adfd": "https://www.adfd.ae/english/Pages/default.aspx",
    "jica": "https://www.jica.go.jp/english/index.html",
}


def check_portals() -> dict[str, str]:
    """Lightweight reachability probe. Does not parse anything."""
    import requests

    banner("PORTAL REACHABILITY CHECK")
    results: dict[str, str] = {}
    for key, url in PROBE_URLS.items():
        if not config.ENABLED_PORTALS.get(key, False):
            results[key] = "disabled"
            continue
        name = config.PORTAL_NAMES.get(key, key)
        try:
            resp = requests.head(
                url, timeout=20, allow_redirects=True,
                headers={"User-Agent": config.USER_AGENT},
            )
            if resp.status_code >= 400:
                resp = requests.get(
                    url, timeout=20, allow_redirects=True,
                    headers={"User-Agent": config.USER_AGENT},
                )
            state = "reachable" if resp.status_code < 400 else f"HTTP {resp.status_code}"
            colour = GREEN if resp.status_code < 400 else YELLOW
            print(f"  {colour}{state:<14}{RESET} {name}")
            results[key] = state
        except Exception as exc:  # noqa: BLE001
            reason = type(exc).__name__
            print(f"  {RED}{'unreachable':<14}{RESET} {name}  ({reason})")
            results[key] = f"unreachable ({reason})"
    return results


# --------------------------------------------------------------------------
# Selector capture / validation
# --------------------------------------------------------------------------
def capture_portal(portal_key: str) -> int:
    """
    Fetch a portal's live pages, save them as fixtures, and report which
    extraction layer actually works and what selectors the page really uses.

    The selector hints in each portal module are informed guesses -- page markup
    could not be retrieved when they were written. Run this once from a machine
    with outbound access to confirm or correct them:

        python run.py --capture ebrd

    Saved pages land in tests/fixtures/live/ and can be committed as permanent
    regression tests.
    """
    from portals import htmlkit

    module = portals.load(portal_key)
    sources = getattr(module, "SOURCES", None)
    if not sources:
        print(f"{RED}{portal_key} has no SOURCES to capture "
              f"(it uses a REST API, not HTML scraping).{RESET}")
        return 1

    out_dir = BASE_DIR / "tests" / "fixtures" / "live"
    out_dir.mkdir(parents=True, exist_ok=True)
    selectors = getattr(module, "SELECTORS", [])
    href_pattern = getattr(module, "HREF_PATTERN", None)

    banner(f"CAPTURE: {config.PORTAL_NAMES.get(portal_key, portal_key)}")
    failures = 0

    for index, source in enumerate(sources, start=1):
        print(f"\n{BOLD}[{index}/{len(sources)}] {source.url}{RESET}")
        try:
            html = htmlkit.fetch_html(source.url, params=source.params, js=source.js)
        except Exception as exc:  # noqa: BLE001
            print(f"  {RED}fetch failed:{RESET} {str(exc)[:150]}")
            failures += 1
            continue

        path = out_dir / f"{portal_key}_{index}.html"
        path.write_text(html, encoding="utf-8")
        print(f"  saved {len(html):,} bytes -> {path.relative_to(BASE_DIR)}")

        report = htmlkit.analyse_page(
            html, source.url, selectors=selectors, href_pattern=href_pattern
        )
        if report["diagnosis"]:
            print(f"  {YELLOW}diagnosis:{RESET} {report['diagnosis']}")

        print(f"  {'layer':<12} {'rows':>5} {'quality':>8}")
        for label, info in report["layers"].items():
            mark = GREEN if info["rows"] else ""
            print(f"  {mark}{label:<12} {info['rows']:>5} {info['quality']:>8.2f}{RESET}"
                  + (f"  {RED}{info['error']}{RESET}" if info.get("error") else ""))

        chosen = report["chosen_layer"]
        colour = GREEN if chosen else RED
        print(f"  {BOLD}chosen:{RESET} {colour}{chosen or 'NOTHING PARSED'}{RESET} "
              f"({report['chosen_rows']} rows)")
        if report["suggested_selectors"]:
            print(f"  {CYAN}selectors this page actually uses:{RESET} "
                  f"{report['suggested_selectors']}")
        if report["next_page"]:
            print(f"  next page: {report['next_page']}")
        for sample in report["layers"].get("structure", {}).get("sample", [])[:3]:
            print(f"    e.g. {sample}")
        if not chosen:
            failures += 1

    print(f"\n{BOLD}Captured {len(sources) - failures}/{len(sources)} sources "
          f"for {portal_key}.{RESET}")
    print("Paste any corrected selectors into "
          f"portals/{portal_key}.py (SELECTORS) and re-run the capture.")
    return 0 if failures < len(sources) else 1


# --------------------------------------------------------------------------
# Scheduling helpers
# --------------------------------------------------------------------------
def print_schedule_instructions() -> None:
    hour, minute = config.SCHEDULE_TIME.split(":")
    script = BASE_DIR / "run.py"
    mode = config.SCHEDULE_MODE

    cron_day = {"daily": "*", "weekly": "1", "mon_thu": "1,4", "once": "*"}.get(mode, "*")
    cron = f"{int(minute)} {int(hour)} * * {cron_day}"

    banner("SCHEDULING")
    print(f"Configured mode: {BOLD}{mode}{RESET} at {config.SCHEDULE_TIME}\n")
    print(f"{BOLD}1. Python (no OS setup){RESET}")
    print(f"   python {script} --schedule\n")
    print(f"{BOLD}2. Linux / macOS cron{RESET}   (crontab -e)")
    print(f"   {cron}  cd {BASE_DIR} && {sys.executable} run.py --send >> cron.log 2>&1\n")
    print(f"{BOLD}3. Windows Task Scheduler{RESET}")
    freq = {"daily": "DAILY", "weekly": "WEEKLY", "mon_thu": "WEEKLY", "once": "ONCE"}.get(mode, "DAILY")
    extra = ' /D MON,THU' if mode == "mon_thu" else (' /D MON' if mode == "weekly" else "")
    print(
        f'   schtasks /Create /TN "JordanTenderMonitor" /TR '
        f'"\\"{sys.executable}\\" \\"{script}\\" --send" /SC {freq}{extra} '
        f'/ST {config.SCHEDULE_TIME}\n'
    )
    print(f"{BOLD}Note{RESET} --send is included so the scheduled run emails the report.")
    print("   Drop it (or use --save-only) if you would rather it only wrote files.\n")


def run_scheduled() -> None:
    import schedule

    job = lambda: execute(send=True)  # noqa: E731
    mode = config.SCHEDULE_MODE
    if mode == "daily":
        schedule.every().day.at(config.SCHEDULE_TIME).do(job)
    elif mode == "weekly":
        getattr(schedule.every(), config.SCHEDULE_WEEKDAY).at(config.SCHEDULE_TIME).do(job)
    elif mode == "mon_thu":
        schedule.every().monday.at(config.SCHEDULE_TIME).do(job)
        schedule.every().thursday.at(config.SCHEDULE_TIME).do(job)
    else:
        job()
        return

    print(f"{GREEN}Scheduler running ({mode} at {config.SCHEDULE_TIME}). Ctrl-C to stop.{RESET}")
    import time

    while True:
        schedule.run_pending()
        time.sleep(30)


# --------------------------------------------------------------------------
# Main pipeline
# --------------------------------------------------------------------------
def execute(
    send: bool = False,
    save_only: bool = False,
    dry_run: bool = False,
    new_only: bool | None = None,
    only_portals: list[str] | None = None,
    fixture_tenders: list[dict] | None = None,
) -> dict:
    scan_time = datetime.now()
    banner(f"JORDAN TENDER INTELLIGENCE  |  {scan_time.strftime('%d %b %Y %H:%M')}")

    check_sam_key()

    # 1-3. Scrape
    self_test = fixture_tenders is not None
    if self_test:
        raw = fixture_tenders
        statuses = [
            scraper.PortalStatus(
                key="fixture", name="Built-in fixtures", ok=True,
                count=len(raw), error=None, seconds=0.0,
            )
        ]
        # A diagnostic must not touch production state. Without this, the
        # fixture IDs would be written to seen_tenders.db, and with new-only
        # mode on a second --self-test would report nothing.
        new_only = False
    else:
        raw, statuses = scraper.scrape_all(only_portals)
    print_portal_table(statuses)

    # 4. Filter, score, dedupe
    tenders, stats = filter_agent.process(raw, new_only=new_only)
    print(
        f"\n{BOLD}Found {len(tenders)} tenders across "
        f"{sum(1 for s in statuses if s['ok'])} reachable portals "
        f"({stats['raw']} raw, {stats['duplicates_merged']} duplicates merged).{RESET}"
    )
    if stats["rejected"]:
        print("  Filtered out: " + ", ".join(f"{n} {r}" for r, n in stats["rejected"].items()))
    print_tender_table(tenders)

    if dry_run:
        print(f"\n{YELLOW}DRY RUN -- no files written, no email sent.{RESET}")
        return {"tenders": tenders, "stats": stats, "statuses": statuses, "dry_run": True}

    # 5. Build report and output files
    outputs = reporter.build_outputs(tenders, statuses, stats, scan_time)
    print(f"\n{BOLD}Files written{RESET}")
    for kind, path in outputs["files"].items():
        print(f"  {GREEN}{kind:<6}{RESET} {path}")

    # 6. Deliver
    delivery = {"sent": False, "method": "skipped"}
    if send and not save_only:
        delivery = emailer.dispatch(
            outputs["subject"], outputs["body_html"],
            attachment=outputs["files"].get("excel"), saved_files=outputs["files"],
        )
        if delivery["sent"]:
            print(f"\n{GREEN}Email sent via {delivery['method']} to "
                  f"{', '.join(delivery['recipients'])}{RESET}")
        else:
            print(f"\n{YELLOW}Email not sent. Attempts: "
                  f"{'; '.join(delivery['attempts']) or 'none configured'}{RESET}")
            print(f"{YELLOW}Report saved in {config.OUTPUT_DIR}{RESET}")
    elif save_only:
        print(f"\n{CYAN}Save-only mode -- no email sent.{RESET}")

    # 7. Record and log. Fixture runs are excluded so a diagnostic never
    # poisons the real seen-tender database.
    written = (
        0 if self_test
        else tracker.record(tenders, scan_time.isoformat(timespec="seconds"))
    )
    log.info(
        "RUN SUMMARY | raw=%d final=%d merged=%d portals_ok=%d/%d email=%s db_rows=%d",
        stats["raw"], stats["final"], stats["duplicates_merged"],
        sum(1 for s in statuses if s["ok"]), len(statuses),
        delivery.get("method"), written,
    )
    return {
        "tenders": tenders, "stats": stats, "statuses": statuses,
        "outputs": outputs, "delivery": delivery,
    }


def load_fixtures() -> list[dict]:
    from fixtures import SAMPLE_TENDERS

    return [dict(t) for t in SAMPLE_TENDERS]


def main() -> int:
    parser = argparse.ArgumentParser(description="Jordan tender intelligence monitor")
    parser.add_argument("--dry-run", action="store_true", help="scrape and print only")
    parser.add_argument("--save-only", action="store_true", help="write files, send no email")
    parser.add_argument("--send", action="store_true", help="send the email without prompting")
    parser.add_argument("--schedule", action="store_true", help="run on the configured schedule")
    parser.add_argument("--cron", action="store_true", help="print scheduling instructions")
    parser.add_argument("--check-portals", action="store_true", help="reachability test only")
    parser.add_argument("--capture", metavar="PORTAL",
                        help="fetch a portal's live pages, save them as fixtures, "
                             "and report which extraction layer and selectors work")
    parser.add_argument("--self-test", action="store_true", help="run against built-in fixtures")
    parser.add_argument("--reset-db", action="store_true", help="clear seen_tenders.db")
    parser.add_argument("--new-only", action="store_true", help="force new-only mode on")
    parser.add_argument("--portals", help="comma-separated portal keys to run")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.reset_db:
        tracker.reset()
        print(f"{GREEN}seen_tenders.db cleared -- the next run will report every open tender.{RESET}")
        return 0

    if args.cron:
        print_schedule_instructions()
        return 0

    if args.check_portals:
        check_portals()
        return 0

    if args.capture:
        key = args.capture.strip().lower()
        if key not in portals.PORTAL_MODULES:
            print(f"{RED}Unknown portal {key!r}.{RESET} Choose one of: "
                  + ", ".join(portals.PORTAL_MODULES))
            return 1
        return capture_portal(key)

    if args.schedule:
        run_scheduled()
        return 0

    only = None
    if args.portals:
        only = [p.strip() for p in args.portals.split(",") if p.strip() in portals.PORTAL_MODULES]

    result = execute(
        send=args.send,
        save_only=args.save_only,
        dry_run=args.dry_run,
        new_only=True if args.new_only else None,
        only_portals=only,
        fixture_tenders=load_fixtures() if args.self_test else None,
    )

    # Interactive confirmation when neither --send nor --save-only was given
    if not args.send and not args.save_only and not args.dry_run and sys.stdin.isatty():
        choice = input("\nSend the report email now, save files only, or cancel? "
                       "(send / save / cancel): ").strip().lower()
        if choice in ("save", "s", "save only", "files"):
            print(f"{CYAN}Files already saved in {config.OUTPUT_DIR}. No email sent.{RESET}")
        elif choice in ("send", "email", "yes", "y"):
            outputs = result["outputs"]
            delivery = emailer.dispatch(
                outputs["subject"], outputs["body_html"],
                attachment=outputs["files"].get("excel"), saved_files=outputs["files"],
            )
            print(f"{GREEN if delivery['sent'] else YELLOW}"
                  f"{'Sent via ' + delivery['method'] if delivery['sent'] else 'Not sent'}{RESET}")
        else:
            print("Cancelled. Files remain in output/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
