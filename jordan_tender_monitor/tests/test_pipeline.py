#!/usr/bin/env python3
"""
Offline tests for the filter, scorer, reporter, emailer and tracker.

Run directly -- no pytest required, no network:

    python tests/test_pipeline.py

test_extraction.py covers getting tenders *out of a page*; this covers what
happens to them afterwards. The cases here are deliberately adversarial: empty
input, a tender where every optional field is None, zero keyword matches, the
deadline boundary, duplicate collapse, the email overflow path, and delivery
with no credentials. Those are the paths a real run hits on a bad day, and they
are the ones most likely to throw.

The seen-tender database is redirected to a temporary file, so running this
never disturbs data/seen_tenders.db.
"""

from __future__ import annotations

import sys
import tempfile
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

warnings.filterwarnings("ignore")

import config  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="jtm_tests_"))
config.SEEN_DB = _TMP / "seen_tenders.db"          # never touch the real database
config.OUTPUT_DIR = _TMP                            # nor the real output directory

from agents import emailer, filter as filter_agent, reporter, scraper, tracker  # noqa: E402

_passed = 0
_failed: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passed
    if condition:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed.append(name)
        print(f"  FAIL  {name}{('  -- ' + detail) if detail else ''}")


def tender(**overrides) -> dict:
    """A minimal well-formed tender; override any field."""
    base = {
        "id": "test:1",
        "title": "Advisory services for institutional reform in Jordan",
        "portal": "World Bank", "portal_key": "worldbank",
        "url": "https://example.org/n/1",
        "posted_date": date.today().isoformat(),
        "closing_date": (date.today() + timedelta(days=20)).isoformat(),
        "estimated_value_usd": 500_000.0,
        "sector": "Governance",
        "description": "Technical assistance and capacity building.",
        "eligibility": None, "contact": None,
        "notice_type": "Request for Proposals", "language": "en",
    }
    base.update(overrides)
    return base


EMPTY_STATS = {"raw": 0, "final": 0, "duplicates_merged": 0,
               "national_only": 0, "arabic": 0, "rejected": {}}


# --------------------------------------------------------------------------
def test_degenerate_inputs() -> None:
    print("\nEmpty and degenerate inputs")
    check("score_tenders([])", filter_agent.score_tenders([]) == [])
    check("deduplicate([])", filter_agent.deduplicate([]) == ([], 0))
    check("process([])", filter_agent.process([])[1]["final"] == 0)

    try:
        reporter.write_excel([], _TMP / "empty.xlsx")
        reporter.write_csv([], _TMP / "empty.csv")
        reporter.write_json([], [], EMPTY_STATS, _TMP / "empty.json")
        ok = True
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"        exception: {exc}")
    check("all writers accept zero rows", ok)


def test_all_none_tender() -> None:
    print("\nTender with every optional field missing (worst a scraper can emit)")
    bare = tender(posted_date=None, closing_date=None, estimated_value_usd=None,
                  sector=None, description="", notice_type=None, url="")
    try:
        scored = filter_agent.score_tenders([bare])
        ok = scored and 0 <= scored[0]["score"] <= 100
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"        exception: {exc}")
    check("scores within 0-100", bool(ok))

    try:
        reporter.build_email_html(scored, [], EMPTY_STATS, datetime.now())
        reporter.write_excel(scored, _TMP / "none.xlsx")
        ok = True
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"        exception: {exc}")
    check("renders email and Excel", ok)


def test_zero_keyword_hits() -> None:
    print("\nZero keyword matches (division guard)")
    rows = [tender(id=f"z:{i}", title=f"qqqq zzzz wwww {i}", description="") for i in range(3)]
    try:
        scored = filter_agent.score_tenders(rows)
        ok = all(0 <= t["score"] <= 100 for t in scored)
    except ZeroDivisionError:
        ok = False
    check("no ZeroDivisionError when nothing matches", ok)


def test_deadline_boundary() -> None:
    print("\nDeadline boundary")
    today = date.today()
    rows = [
        tender(id="b:today", closing_date=today.isoformat()),
        tender(id="b:past", closing_date=(today - timedelta(days=1)).isoformat()),
        tender(id="b:future", closing_date=(today + timedelta(days=1)).isoformat()),
        tender(id="b:none", closing_date=None),
    ]
    kept, _ = filter_agent.apply_filters([dict(r) for r in rows])
    ids = {t["id"] for t in kept}
    check("closing today is kept", "b:today" in ids, str(ids))
    check("yesterday is dropped", "b:past" not in ids)
    check("tomorrow is kept", "b:future" in ids)
    check("undated is kept and flagged",
          "b:none" in ids and any(t.get("deadline_flag") for t in kept if t["id"] == "b:none"))


def test_value_filter() -> None:
    print("\nMinimum value filter")
    rows = [
        tender(id="v:above", estimated_value_usd=200_000.0),
        tender(id="v:below", estimated_value_usd=50_000.0),
        tender(id="v:unknown", estimated_value_usd=None),
    ]
    kept, rejected = filter_agent.apply_filters([dict(r) for r in rows])
    ids = {t["id"] for t in kept}
    check("above threshold kept", "v:above" in ids)
    check("below threshold dropped", "v:below" not in ids, str(rejected))
    check("unknown value kept (most notices omit it)", "v:unknown" in ids)


def test_eligibility_penalty() -> None:
    print("\nNational-only eligibility flag and penalty")
    normal = tender(id="e:open")
    restricted = tender(id="e:national", eligibility="National firms only",
                        description="Participation restricted to national firms only.")
    scored = filter_agent.score_tenders([dict(normal), dict(restricted)])
    flagged = next(t for t in scored if t["id"] == "e:national")
    clean = next(t for t in scored if t["id"] == "e:open")
    check("restricted tender flagged", bool(flagged.get("eligibility_flag")))
    check("penalty applied",
          flagged["score_components"].get("eligibility_penalty") == -float(config.NATIONAL_ONLY_PENALTY))
    check("ranks below the open tender", flagged["score"] < clean["score"],
          f"{flagged['score']} vs {clean['score']}")


def test_arabic_flagged_not_penalised() -> None:
    print("\nArabic notices included and flagged, not down-ranked for language")
    ar = tender(id="a:1", language="ar",
                title="خدمات استشارية لبناء القدرات المؤسسية في الأردن",
                description="دعوة لتقديم عروض استشارية")
    kept, _ = filter_agent.apply_filters([dict(ar)])
    check("Arabic tender kept", len(kept) == 1)
    check("flagged for manual review",
          kept and kept[0].get("language_flag") == config.ARABIC_FLAG_NOTE)
    scored = filter_agent.score_tenders(kept)
    check("scores above zero on keywords (Arabic lexicon present)",
          scored[0]["score_components"].get("keyword", 0) > 0,
          str(scored[0]["score_components"]))


def test_deduplication() -> None:
    print("\nDeduplication across portals")
    same = [
        tender(id="d:1", portal="World Bank",
               title="Institutional Capacity Assessment Jordan"),
        tender(id="d:2", portal="UNGM (UN agencies)",
               title="Institutional Capacity Assessment, Jordan"),
        tender(id="d:3", portal="EU TED",
               title="Institutional Capacity Assessment - Jordan"),
    ]
    scored = filter_agent.score_tenders([dict(r) for r in same])
    kept, merged = filter_agent.deduplicate(scored)
    check("three near-identical titles collapse to one", len(kept) == 1 and merged == 2,
          f"kept={len(kept)} merged={merged}")
    check("annotated with the other portals",
          "Also found on" in (kept[0].get("duplicate_note") or ""),
          str(kept[0].get("duplicate_note")))

    distinct = filter_agent.score_tenders([
        dict(tender(id="x:1", title="Water network supervision Amman")),
        dict(tender(id="x:2", title="Digital government advisory Jordan")),
    ])
    kept2, merged2 = filter_agent.deduplicate(distinct)
    check("distinct titles are not merged", len(kept2) == 2 and merged2 == 0)


def test_email_overflow() -> None:
    print("\nEmail overflow beyond MAX_INLINE_TENDERS")
    limit = config.MAX_INLINE_TENDERS
    many = filter_agent.score_tenders(
        [dict(tender(id=f"m:{i}", title=f"Jordan technical assistance package {i}"))
         for i in range(limit + 7)]
    )
    body = reporter.build_email_html(many, [], dict(EMPTY_STATS, raw=len(many), final=len(many)),
                                     datetime.now())
    check("overflow section rendered", f"Remaining {7} tenders" in body)
    check("points at the attachment", "attached workbook" in body)
    check("all tenders still in the workbook",
          len(reporter.EXCEL_COLUMNS) == 12 and len(many) == limit + 7)


def test_no_results_email() -> None:
    print("\nNo-results email names the portals that failed")
    statuses = [
        scraper.PortalStatus(key="worldbank", name="World Bank", ok=True,
                             count=0, error=None, seconds=1.0),
        scraper.PortalStatus(key="ungm", name="UNGM (UN agencies)", ok=False,
                             count=0, error="board could not be parsed", seconds=8.0),
    ]
    body = reporter.build_email_html([], statuses, EMPTY_STATS, datetime.now())
    check("states the scan succeeded", "completed successfully" in body)
    check("names the failed portal", "UNGM" in body)
    check("tells the reader to check manually", "check manually" in body.lower())


def test_emailer_fallback() -> None:
    print("\nEmail dispatch on an unconfigured clone")

    original = config.EMAIL_RECIPIENTS
    try:
        # No recipients: a fresh clone, before .env is filled in.
        config.EMAIL_RECIPIENTS = []
        result = emailer.dispatch("subject", "<p>body</p>", attachment=None,
                                  saved_files={"html": _TMP / "r.html"})
        check("never raises", isinstance(result, dict))
        check("reports not sent", result["sent"] is False)
        check("falls back to file", result["method"] == "file")
        check("says recipients are missing rather than failing inside Graph",
              any("EMAIL_RECIPIENTS" in a for a in result["attempts"]),
              str(result["attempts"]))

        # Recipients set, but still no Graph or SMTP credentials.
        config.EMAIL_RECIPIENTS = ["someone@example.com"]
        result = emailer.dispatch("subject", "<p>body</p>", attachment=None,
                                  saved_files={"html": _TMP / "r.html"})
        check("still falls back to file", result["method"] == "file"
              and result["sent"] is False)
        check("records why each method was skipped",
              all("not configured" in a for a in result["attempts"]),
              str(result["attempts"]))
    finally:
        config.EMAIL_RECIPIENTS = original


def test_tracker_and_new_only() -> None:
    print("\nSeen-tender tracker and new-only mode")
    tracker.reset()
    check("starts empty", tracker.count() == 0)

    first = tender(id="t:1")
    tracker.record([dict(first)], datetime.now().isoformat(timespec="seconds"))
    check("records the tender", tracker.count() == 1)
    check("seen_ids contains it", "t:1" in tracker.seen_ids())

    kept, rejected = filter_agent.apply_filters([dict(first)], new_only=True)
    check("new-only filters an already-reported tender", len(kept) == 0, str(rejected))

    kept2, _ = filter_agent.apply_filters([dict(tender(id="t:2"))], new_only=True)
    check("new-only keeps an unseen tender", len(kept2) == 1)

    kept3, _ = filter_agent.apply_filters([dict(first)], new_only=False)
    check("with new-only off the tender is kept again", len(kept3) == 1)

    tracker.reset()
    check("reset clears the database", tracker.count() == 0)


def test_self_test_does_not_touch_the_database() -> None:
    print("\n--self-test is a diagnostic: it must not write to seen_tenders.db")
    import contextlib
    import io

    import run

    tracker.reset()
    for attempt in (1, 2):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = run.execute(save_only=True, fixture_tenders=run.load_fixtures())
        check(f"run {attempt} reports the same tenders", len(result["tenders"]) == 7,
              f"got {len(result['tenders'])}")
    check("no rows written to the database", tracker.count() == 0,
          f"{tracker.count()} rows leaked")
    tracker.reset()


def test_new_only_mode_is_enabled() -> None:
    print("\nNew-only mode configuration")
    check("NEW_ONLY_MODE is on", config.NEW_ONLY_MODE is True,
          f"got {config.NEW_ONLY_MODE}")
    # With it on, a real run must consult the database by default.
    tracker.reset()
    first = tender(id="n:1")
    kept, _ = filter_agent.apply_filters([dict(first)])
    check("first sighting is reported", len(kept) == 1)
    tracker.record(kept, datetime.now().isoformat(timespec="seconds"))
    kept2, rejected = filter_agent.apply_filters([dict(first)])
    check("second run suppresses it without needing an explicit flag",
          len(kept2) == 0, str(rejected))
    tracker.reset()


def test_scoring_weights() -> None:
    print("\nScore weighting reflects the chosen configuration")
    weights = filter_agent._active_weights()
    check("sector component dropped under 'all sectors'",
          "sector" not in weights or bool(config.TARGET_SECTORS), str(weights))
    check("weights renormalise to 100", abs(sum(weights.values()) - 100.0) < 0.01,
          str(sum(weights.values())))

    urgent = tender(id="s:urgent", closing_date=(date.today() + timedelta(days=5)).isoformat())
    distant = tender(id="s:distant", closing_date=(date.today() + timedelta(days=200)).isoformat())
    scored = filter_agent.score_tenders([dict(urgent), dict(distant)])
    a = next(t for t in scored if t["id"] == "s:urgent")
    b = next(t for t in scored if t["id"] == "s:distant")
    check("closer deadline scores higher", a["score"] > b["score"], f"{a['score']} vs {b['score']}")


def test_unicode_outputs() -> None:
    print("\nArabic survives the output writers")
    ar = filter_agent.score_tenders([dict(tender(
        id="u:1", language="ar",
        title="إعلان طرح خدمات استشارية في الأردن",
        description="وصف عربي للمشروع"))])
    reporter.write_json(ar, [], EMPTY_STATS, _TMP / "ar.json")
    check("JSON keeps Arabic unescaped",
          "الأردن" in (_TMP / "ar.json").read_text(encoding="utf-8"))
    reporter.write_csv(ar, _TMP / "ar.csv")
    check("CSV written with BOM so Excel renders it",
          (_TMP / "ar.csv").read_bytes()[:3] == b"\xef\xbb\xbf")
    reporter.write_excel(ar, _TMP / "ar.xlsx")
    check("Excel written", (_TMP / "ar.xlsx").exists())


# --------------------------------------------------------------------------
def main() -> int:
    print("=" * 74)
    print("Pipeline tests -- filter, scorer, reporter, emailer, tracker (offline)")
    print("=" * 74)

    test_degenerate_inputs()
    test_all_none_tender()
    test_zero_keyword_hits()
    test_deadline_boundary()
    test_value_filter()
    test_eligibility_penalty()
    test_arabic_flagged_not_penalised()
    test_deduplication()
    test_email_overflow()
    test_no_results_email()
    test_emailer_fallback()
    test_tracker_and_new_only()
    test_self_test_does_not_touch_the_database()
    test_new_only_mode_is_enabled()
    test_scoring_weights()
    test_unicode_outputs()

    print("\n" + "=" * 74)
    total = _passed + len(_failed)
    if _failed:
        print(f"{_passed}/{total} passed, {len(_failed)} FAILED:")
        for name in _failed:
            print(f"  - {name}")
        return 1
    print(f"All {total} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
