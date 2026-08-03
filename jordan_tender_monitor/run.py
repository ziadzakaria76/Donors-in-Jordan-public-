#!/usr/bin/env python3
"""
Jordan Tender Intelligence Monitor -- command line entry point.

    python run.py --check-portals   are the portals reachable from this machine?
    python run.py --dry-run         scrape, filter, print. Change no state.
    python run.py --run             the real run: write the Word and Excel files
                                    into output/ and record what was reported
                                    (--send is kept as an alias)
    python run.py --capture PORTAL  fetch a portal's live pages and report
                                    which extraction layer works
    python run.py --self-test       run the pipeline on offline fixtures
    python run.py --test-alert      prove the failure-alert path works
    python run.py --reset-db        forget every reported tender
    python run.py --schedule        run on the configured schedule

--self-test and the test suite redirect the database and output directory to a
temporary folder. A diagnostic that wrote fixture IDs into the real
seen-tenders database would make the next live run report nothing, and a
monitor that reports nothing looks broken in exactly the same way as a monitor
that is broken.
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jordan_tender_monitor import config  # noqa: E402
from jordan_tender_monitor.agents import (emailer, filter as filters,  # noqa: E402
                                          reporter, scraper, tracker)

log = logging.getLogger("jtm")


def setup_logging(verbose: bool = False) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(config.LOG_FILE, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        config.refresh_credentials()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_check_portals() -> int:
    from jordan_tender_monitor import portals

    print(f"\nChecking {len(portals.enabled())} portals from this machine...\n")
    health = scraper.check_portals()

    width = max(len(h.name) for h in health)
    broken = 0
    for h in health:
        if h.status == "ok":
            detail = f"{h.count} Jordan notice(s)"
            if h.scanned is not None and h.scanned != h.count:
                detail += f" of {h.scanned} read"
            detail += f" via {h.layer or 'api'}"
            mark = "OK        "
        elif h.status == "unconfigured":
            mark, detail = "NOT SET UP", h.reason
        else:
            mark, detail = "UNREACHABLE", h.reason
            broken += 1
        print(f"  [{mark:11}] {h.name:{width}}  {detail}")
        if h.status == "unavailable" and h.urls:
            print(f"{'':16}{'':{width}}  check by hand: {h.urls[0]}")

    total = len([h for h in health if h.status != "unconfigured"])
    print(f"\n{total - broken}/{total} portals reachable.\n")
    if broken == total and total:
        print("Every portal was unreachable. That usually means the network or an "
              "egress policy is blocking them, not that all thirteen sites changed "
              "at once.\n")
    return 0 if broken < total else 1


def cmd_capture(portal_key: str) -> int:
    from jordan_tender_monitor import portals
    from jordan_tender_monitor.portals.htmlkit import QUALITY_THRESHOLD

    capturable = portals.html_portals()
    if portal_key not in capturable:
        print(f"'{portal_key}' is not an HTML portal. Capturable portals:\n  "
              + "\n  ".join(sorted(capturable)))
        return 2

    config.LIVE_FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nCapturing {portals.name(portal_key)}...\n")

    module = capturable[portal_key]
    results = module.capture()
    any_saved = False

    for index, (url, html, layers) in enumerate(results, start=1):
        print(f"  Source {index}: {url}")
        if not html:
            print(f"    FAILED: {layers[0].note if layers else 'no content'}\n")
            continue

        path = config.LIVE_FIXTURE_DIR / f"{portal_key}_{index}.html"
        path.write_text(html, encoding="utf-8")
        any_saved = True
        print(f"    saved {len(html):,} bytes -> {path}")

        print(f"    {'layer':16} {'rows':>5} {'quality':>8}  note")
        winner = None
        for layer in layers:
            flag = ""
            if winner is None and layer.rows and layer.quality >= QUALITY_THRESHOLD:
                winner, flag = layer, "  <-- WINS"
            print(f"    {layer.layer:16} {len(layer.rows):5} {layer.quality:8.2f}  "
                  f"{layer.note[:60]}{flag}")

        if winner is None:
            print("    No layer cleared the quality gate. Diagnosis:")
            from jordan_tender_monitor.portals.htmlkit import diagnose
            print(f"      {diagnose(html, [])}")
        else:
            print(f"\n    Sample row from the winning '{winner.layer}' layer:")
            row = winner.rows[0]
            print(f"      title   : {row.title[:90]}")
            print(f"      url     : {row.url}")
            print(f"      posted  : {row.date_text}")
            print(f"      closing : {row.closing_text}")
            print(f"      value   : {(row.value_text or '')[:70]}")

        print("\n    Selectors this page actually uses (derived structurally):")
        for hint in _derive_selectors(html):
            print(f"      {hint}")

        for line in _describe_tables(html):
            print(f"      {line}")
        print()

    if not any_saved:
        print("Nothing was captured -- every source URL failed. The portal is "
              "unreachable from here, so its selectors cannot be verified.\n")
        return 1
    return 0


def _derive_selectors(html: str, limit: int = 6) -> list[str]:
    """Report the repeated-block selectors the page really uses.

    Derived from the DOM rather than guessed, so the output can be pasted
    straight into a portal module's selector list.
    """
    from collections import Counter

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    counter: Counter[str] = Counter()
    for node in soup.find_all(True):
        classes = node.get("class") or []
        if not classes:
            continue
        if not node.find("a", href=True):
            continue
        counter["{}.{}".format(node.name, ".".join(sorted(classes)[:2]))] += 1

    out = [f"{sel}    ({n} matching blocks)"
           for sel, n in counter.most_common(limit * 3) if n >= 3][:limit]
    return out or ["(no repeated class-bearing blocks -- this page needs the "
                   "class-independent layers)"]


def _describe_tables(html: str, limit: int = 2) -> list[str]:
    """Show how each table's header maps onto columns, and one row's cells.

    A header can map correctly and the row still come out wrong -- nested
    tables, colspans and responsive duplicate cells all shift the indices. The
    per-layer summary cannot show that; only the cells side by side can.
    """
    from bs4 import BeautifulSoup

    from jordan_tender_monitor.portals.htmlkit import _match_header
    from jordan_tender_monitor.utils.text import clean, truncate

    out: list[str] = []
    soup = BeautifulSoup(html, "html.parser")
    for index, table in enumerate(soup.find_all("table")[:limit], start=1):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        header = [clean(c.get_text()) for c in rows[0].find_all(["th", "td"])]
        if not header:
            continue
        out.append(f"\n    Table {index}: {len(rows) - 1} data row(s), "
                   f"{len(header)} header cell(s)")
        for i, cell in enumerate(header):
            mapped = _match_header(cell) or "-"
            out.append(f"      [{i}] {mapped:9} header={truncate(cell, 40)!r}")

        body = table.find("tbody") or table
        data = [r for r in body.find_all("tr") if r is not rows[0]]
        if data:
            cells = [clean(c.get_text(" ")) for c in data[0].find_all(["td", "th"])]
            out.append(f"      first data row has {len(cells)} cell(s)"
                       + ("  <-- MISMATCH with the header" if len(cells) != len(header) else ""))
            for i, cell in enumerate(cells):
                out.append(f"      [{i}] {truncate(cell, 70)!r}")
    return out


def _run_pipeline(only: list[str] | None = None):
    result_scrape = scraper.scrape(only)
    processed = filters.process(result_scrape.records)
    return result_scrape, processed


def _print_summary(scrape_result, processed, reported: list[dict]) -> None:
    print("\n" + "=" * 78)
    print(f"Scanned {processed['scanned']} notices across "
          f"{len(scrape_result.health)} portals")
    print(f"Passed filters: {len(processed['tenders'])}   "
          f"Merged duplicates: {processed['merged_duplicates']}   "
          f"New this run: {len(reported)}")
    if processed["dropped"]:
        print("Filtered out: " + ", ".join(f"{v} {k}" for k, v in
                                           sorted(processed["dropped"].items())))
    print("=" * 78)

    for t in reported[:25]:
        flags = f"  [{'; '.join(t['flags'])}]" if t.get("flags") else ""
        print(f"\n  [{t['score']:5.1f}] {t['title'][:88]}")
        print(f"          {t['portal_name']} | {t['sector']} | "
              f"deadline {t['closing_display']} | {t['value_display']}{flags}")
        if t.get("url"):
            print(f"          {t['url']}")
    if len(reported) > 25:
        print(f"\n  ... and {len(reported) - 25} more (all of them are in the "
              f"output files)")

    print("\n" + "-" * 78)
    print("Portal status")
    for h in scrape_result.health:
        if h.status == "ok":
            extra = ""
            if h.scanned is not None and h.scanned != h.count:
                extra = f"  ({h.scanned} read, {h.scanned - h.count} not Jordan)"
            print(f"  OK          {h.name}: {h.count}{extra}")
        elif h.status == "unconfigured":
            print(f"  NOT SET UP  {h.name}: {h.reason}")
        else:
            print(f"  UNAVAILABLE {h.name}: {h.reason}")
            if h.urls:
                print(f"              check: {h.urls[0]}")
    print("-" * 78 + "\n")


def _warn_if_alerting_is_blind() -> None:
    """Say so when alerting is enabled but could not actually send.

    Printed on every real run, not only on failing ones -- an alert path is
    only worth having if you know it works before you need it.
    """
    if not config.ALERT_EMAIL:
        return
    ok, detail = emailer.alert_configured()
    if not ok:
        print(f"\n  NOTE: failure alerting is enabled but cannot send - {detail}.\n"
              f"        Runs will still write their files, and the filename will "
              f"still state the run's health,\n"
              f"        but nothing will reach your inbox if the scrapers break. "
              f"Verify with: python run.py --test-alert\n")


def cmd_run(send: bool, only: list[str] | None = None,
            fail_on_alert: bool = False) -> int:
    store = tracker.Tracker()
    first_run = store.is_first_run()

    scrape_result, processed = _run_pipeline(only)
    reported = store.filter_new(processed["tenders"])
    reporter.decorate(reported)
    reporter.decorate(processed["tenders"])

    display = dict(processed)
    display["tenders"] = reported

    subject = reporter.build_subject(len(reported), scrape_result.health, first_run)
    body_html = reporter.build_email_html(display, scrape_result.health, first_run)
    body_text = reporter.build_text_body(display, scrape_result.health)

    _print_summary(scrape_result, processed, reported)
    print(f"Subject line would be:\n    {subject}\n")

    written = reporter.write_outputs(display, scrape_result.health, body_html)
    for name, path in written.items():
        print(f"  wrote {name:6} {path}")

    if not send:
        print("\nDry run. The files above were written, but nothing was recorded "
              "as seen,\nso the next run will report these same tenders again. "
              "Use --run for the real thing.\n")
        return 0

    _send_alert_if_needed(scrape_result.health, written)

    attachments = reporter.attachments_for_email(written)
    delivery = emailer.deliver(subject, body_html, body_text, attachments, written)
    if delivery.method == "file":
        print(f"\nSaved to disk. {delivery.detail}")
    else:
        print(f"\nDelivery via {delivery.method}: {delivery.detail}")

    # Only record as seen once the report has actually gone out. Recording
    # first would lose a run's tenders permanently if delivery failed.
    if delivery.sent:
        store.record(reported)
        store.log_run(processed["scanned"], len(reported),
                      len(scrape_result.ok_portals), len(scrape_result.health))

    # A non-zero exit turns a CI run red, which is how a total outage becomes
    # visible on a phone: GitHub shows a failed run and notifies you, with no
    # mail credentials involved. Off by default so a local run is not confusing.
    if fail_on_alert:
        needed, reason = emailer.should_alert(scrape_result.health)
        if needed:
            print(f"\nExiting non-zero: {reason}. The files were still written.")
            return 2
    return 0


def _send_alert_if_needed(health: list, written: dict) -> None:
    """Send the ACTION NEEDED alert, if this run warrants one.

    Called after the files are written, so a failure here can never cost the
    report. Any outcome is printed: a silently unsent alert would defeat the
    purpose of having one.
    """
    needed, reason = emailer.should_alert(health)
    if not needed:
        return

    subject, html_body, text_body = reporter.build_alert(health, reason, written)
    result = emailer.send_alert(subject, html_body, text_body)
    if result.sent:
        print(f"\n  ALERT SENT ({reason}) via {result.method}.")
    else:
        print(f"\n  *** THIS RUN NEEDED ATTENTION ({reason}) AND THE ALERT COULD "
              f"NOT BE SENT ***\n      {result.detail}\n"
              f"      Fix the mail configuration, or watch "
              f"{config.OUTPUT_DIR} by hand.\n")


def cmd_test_alert() -> int:
    """Send a specimen alert so the path is proven before it is relied on."""
    from jordan_tender_monitor import fixtures

    ok, detail = emailer.alert_configured()
    print(f"\nAlert configuration: {'OK -- via ' + detail if ok else 'NOT USABLE'}")
    if not ok:
        print(f"  {detail}\n\nNothing was sent. Fix .env and try again.\n")
        return 1

    health = fixtures.all_broken_health()
    needed, reason = emailer.should_alert(health)
    subject, html_body, text_body = reporter.build_alert(health, reason or "test")
    print(f"  recipients : {', '.join(config.alert_recipients())}")
    print(f"  subject    : {subject}")

    result = emailer.send_alert("[TEST] " + subject, html_body, text_body)
    if result.sent:
        print(f"\nTest alert sent via {result.method}. Confirm it arrived -- and "
              f"check it is not filtered as spam.\n")
        return 0
    print(f"\nTest alert FAILED: {result.detail}\n")
    return 1


def cmd_self_test() -> int:
    """Run the full pipeline on offline fixtures, in a throwaway directory."""
    from jordan_tender_monitor import fixtures

    with tempfile.TemporaryDirectory(prefix="jtm-selftest-") as tmp:
        tmpdir = Path(tmp)
        original_output = config.OUTPUT_DIR
        config.OUTPUT_DIR = tmpdir / "output"
        config.OUTPUT_DIR.mkdir(parents=True)

        # A throwaway database. The real one is never opened by this command.
        store = tracker.Tracker(tmpdir / "seen.db")

        records = fixtures.sample_records()
        health = fixtures.sample_health()
        processed = filters.process(records)
        reported = store.filter_new(processed["tenders"])
        reporter.decorate(reported)
        display = dict(processed)
        display["tenders"] = reported

        subject = reporter.build_subject(len(reported), health, store.is_first_run())
        body = reporter.build_email_html(display, health, True)
        written = reporter.write_outputs(display, health, body, config.OUTPUT_DIR)

        print(f"\nSelf-test on offline fixtures (temp dir: {tmpdir})")
        print(f"  records in       : {len(records)}")
        print(f"  passed filters   : {len(processed['tenders'])}")
        print(f"  reported         : {len(reported)}")
        print(f"  subject          : {subject}")
        print(f"  files written    : {', '.join(sorted(written)) or 'none'}")
        print(f"  real database    : untouched ({config.SEEN_DB})")
        config.OUTPUT_DIR = original_output

        ok = bool(reported) and len(written) == len(config.OUTPUT_FORMATS)
        print(f"\nSelf-test {'PASSED' if ok else 'FAILED'}\n")
        return 0 if ok else 1


def cmd_reset_db() -> int:
    store = tracker.Tracker()
    removed = store.reset()
    print(f"Forgot {removed} recorded tender(s). The next run reports the full "
          f"open pipeline once, then returns to new-only.")
    return 0


def _runs_today(now: datetime) -> bool:
    """Whether the configured schedule fires on this weekday (Mon=0)."""
    mode = config.SCHEDULE_MODE
    if mode == "weekdays":
        return now.weekday() < 5
    if mode == "weekly":
        return now.weekday() == 0
    if mode == "mon_thu":
        return now.weekday() in (0, 3)
    return True  # "daily" and "once"


def cmd_schedule() -> int:
    """Run on the configured schedule, pinned to Asia/Amman.

    Jordan is UTC+3 year-round -- it abolished DST in 2022 -- so 07:00 on a UTC
    host would fire at 10:00 in Amman. The timezone is pinned rather than
    inherited from the host clock, so moving the machine does not silently
    shift the run by three hours.
    """
    import time

    try:
        tz = ZoneInfo(config.SCHEDULE_TIMEZONE)
    except ZoneInfoNotFoundError:
        # Windows ships no system time zone database, so zoneinfo falls back to
        # the tzdata package. Without it this raises on startup with a message
        # that gives no hint what to install.
        print(f"\nCannot load the time zone '{config.SCHEDULE_TIMEZONE}'.\n\n"
              "This host has no IANA time zone database. On Windows that is "
              "normal and the fix is:\n\n"
              "    pip install tzdata\n\n"
              "(It is already in requirements.txt for Windows; this means the "
              "install was incomplete.)\n", file=sys.stderr)
        return 2
    hour, minute = (int(p) for p in config.SCHEDULE_TIME.split(":"))
    print(f"Scheduler running. {config.SCHEDULE_MODE} at {config.SCHEDULE_TIME} "
          f"{config.SCHEDULE_TIMEZONE}.")
    print(f"Equivalent cron on a UTC host:  {config.SCHEDULE_CRON_UTC}  "
          f"(python {Path(__file__).resolve()} --send)")
    print("Ctrl-C to stop.\n")

    last_run: date | None = None
    while True:
        now = datetime.now(tz)
        due = ((now.hour, now.minute) >= (hour, minute)
               and now.date() != last_run
               and _runs_today(now))
        if due:
            log.info("scheduled run starting (%s)", now.isoformat(timespec="minutes"))
            try:
                cmd_run(send=True)
            except Exception:  # noqa: BLE001 - the scheduler must survive a bad run
                log.exception("scheduled run failed")
            last_run = now.date()
        time.sleep(30)


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Jordan Tender Intelligence Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-portals", action="store_true",
                       help="test reachability of every enabled portal")
    group.add_argument("--dry-run", action="store_true",
                       help="scrape, filter and print; record nothing as seen")
    group.add_argument("--run", "--send", action="store_true", dest="send",
                       help="the real run: write the report files into output/ "
                            "and record what was reported. Sends email only if "
                            "EMAIL_METHOD is configured (it is off by default)")
    group.add_argument("--capture", metavar="PORTAL",
                       help="fetch a portal's live pages and report which "
                            "extraction layer works")
    group.add_argument("--self-test", action="store_true",
                       help="run the pipeline on offline fixtures in a temp dir")
    group.add_argument("--test-alert", action="store_true",
                       help="send a specimen ACTION NEEDED alert, to prove the "
                            "alert path works before you rely on it")
    group.add_argument("--reset-db", action="store_true",
                       help="forget every reported tender")
    group.add_argument("--schedule", action="store_true",
                       help="run continuously on the configured schedule")
    parser.add_argument("--fail-on-alert", action="store_true",
                        help="exit non-zero when the run needs attention, so a "
                             "CI job turns red. Files are still written")
    parser.add_argument("--only", nargs="+", metavar="PORTAL",
                        help="restrict to these portals")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    load_env()

    if args.send:
        _warn_if_alerting_is_blind()
    if args.check_portals:
        return cmd_check_portals()
    if args.capture:
        return cmd_capture(args.capture)
    if args.test_alert:
        return cmd_test_alert()
    if args.self_test:
        return cmd_self_test()
    if args.reset_db:
        return cmd_reset_db()
    if args.schedule:
        return cmd_schedule()
    return cmd_run(send=args.send, only=args.only,
                   fail_on_alert=args.fail_on_alert)


if __name__ == "__main__":
    sys.exit(main())
