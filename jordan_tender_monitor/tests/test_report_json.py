"""
The JSON report: the Android app's only view of a run.

GitHub's REST API does not expose a job's step summary -- summaries live in an
internal container the artifacts API does not list -- so the markdown rendered
onto the run page cannot be read by a client. The app downloads this file from
the run's artifacts instead, and everything it can ever show comes out of it.

That makes this a CONTRACT, and the tests here are about the properties a
contract needs rather than about JSON serialising correctly:

  * every field the app renders is present, so a screen cannot go blank for a
    reason no one can see;
  * a quiet run and a broken run are different documents, not the same document
    with a different number in it;
  * `scanned` stays null when a portal never filtered, because rendering it as
    0 would destroy the one signal that separates "read nothing" from "read 500
    and none were Jordan";
  * Arabic survives as Arabic.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from jordan_tender_monitor import config, fixtures
from jordan_tender_monitor.agents import filter as filters, reporter
from jordan_tender_monitor.agents.scraper import PortalHealth
from jordan_tender_monitor.portals import base

from .harness import check, check_eq

# What the app reads off every opportunity row. Named here rather than left
# implicit: a field quietly dropped from the pipeline would otherwise show up
# as an empty line on a phone and nowhere else.
TENDER_FIELDS = ("id", "title", "portal", "portal_name", "url", "score",
                 "sector", "notice_type", "language", "flags",
                 "posted_date", "closing_date", "days_left",
                 "estimated_value_usd", "value_display", "eligibility",
                 "contact", "description", "country", "delivery_country")

PORTAL_FIELDS = ("key", "name", "tier", "tier_label", "status", "count",
                 "scanned", "reason", "urls", "layer", "quality")


def _all_ok() -> list:
    """A run where every portal was read. sample_health() has one broken."""
    return [h for h in fixtures.sample_health() if h.status == "ok"]


def _write(tenders, health, result=None) -> dict:
    with tempfile.TemporaryDirectory(prefix="jtm-json-") as tmp:
        path = Path(tmp) / "report.json"
        reporter.write_json(tenders, health, path, result)
        return json.loads(path.read_text(encoding="utf-8"))


def _report(records=None, health=None) -> dict:
    records = fixtures.sample_records() if records is None else records
    health = fixtures.sample_health() if health is None else health
    result = filters.process(records)
    reporter.decorate(result["tenders"])
    return _write(result["tenders"], health, result)


def test_the_app_can_render_every_row_without_guessing():
    payload = _report()
    check_eq(payload["schema"], reporter.REPORT_SCHEMA,
             "report: the schema version is stated, so an app can refuse a "
             "document it was not written for")
    check(payload.get("generated_at"), "report: it says when it was written")
    check(payload["tenders"], "report: there are opportunities to render")

    for tender in payload["tenders"]:
        for field in TENDER_FIELDS:
            check(field in tender,
                  f"report: every opportunity carries '{field}'",
                  f"missing on {tender.get('title')!r}")
        check(isinstance(tender["flags"], list),
              "report: flags are a list, so the app never splits a string")

    check_eq(payload["tender_count"], len(payload["tenders"]),
             "report: the count and the list agree")


def test_every_portal_is_in_the_table_in_full():
    """The status table is the honesty mechanism; it must not be summarised."""
    health = fixtures.sample_health()
    payload = _report(health=health)

    check_eq(len(payload["portals"]), len(health),
             "report: every portal appears, including the quiet ones")
    for portal in payload["portals"]:
        for field in PORTAL_FIELDS:
            check(field in portal,
                  f"report: every portal carries '{field}'",
                  f"missing on {portal.get('key')}")

    by_key = {p["key"]: p for p in payload["portals"]}
    check_eq(by_key["ebrd"]["status"], "unavailable",
             "report: a broken portal is marked broken")
    check("bot wall" in by_key["ebrd"]["reason"],
          "report: with the diagnosed reason, not just a red dot")
    check(by_key["ebrd"]["urls"],
          "report: and the URL to check by hand")
    check_eq(by_key["samgov"]["status"], "unconfigured",
             "report: a missing API key stays distinct from a failure")
    check_eq(by_key["giz"]["layer"], "table",
             "report: the winning extraction layer is carried")
    check(by_key["giz"]["quality"] > 0,
          "report: and its quality score, so a weak read is visible")


def test_an_unknown_deadline_is_null_rather_than_an_empty_string():
    """A missing field is not evidence, and JSON is typed where a table is not.

    `days_left` is "" in the Word and Excel output because that is what belongs
    in a cell. In JSON it has to be null: "" would need special-casing at every
    call site on the phone, and the one that got missed would render an unknown
    deadline as a real value.
    """
    payload = _report()
    undated = [t for t in payload["tenders"] if t.get("closing_date") is None]
    check(undated, "report: the fixtures include a notice with no deadline")
    for tender in undated:
        check(tender["days_left"] is None,
              "report: no deadline means days_left is null, not \"\" and not 0",
              f"got {tender['days_left']!r}")
    dated = [t for t in payload["tenders"] if t.get("closing_date")]
    check(all(isinstance(t["days_left"], int) for t in dated),
          "report: and a real deadline yields a real number")


def test_scanned_stays_null_rather_than_becoming_zero():
    """The distinction five identical zeroes could not make.

    "OK: 0" cannot say whether a portal returned nothing or returned 500
    worldwide notices of which none were Jordan, and those need entirely
    different fixes. A null here means "this portal never filters, so the
    question does not apply" -- and 0 would mean something else entirely.
    """
    health = [
        PortalHealth("a", "Never filters", 2, "ok", count=0, scanned=None),
        PortalHealth("b", "Read 500, kept none", 2, "ok", count=0, scanned=500),
    ]
    payload = _write([], health)
    by_key = {p["key"]: p for p in payload["portals"]}
    check(by_key["a"]["scanned"] is None,
          "report: a portal that never filtered reports null, not 0",
          f"got {by_key['a']['scanned']!r}")
    check_eq(by_key["b"]["scanned"], 500,
             "report: and one that filtered reports what it read")


def test_a_quiet_run_and_a_broken_run_are_different_documents():
    """'0 opportunities' and 'nothing could be read' must never render alike."""
    quiet = _write([], _all_ok(),
                   {"scanned": 812, "merged_duplicates": 0, "dropped": {}})
    dead = _write([], fixtures.all_broken_health(),
                  {"scanned": 0, "merged_duplicates": 0, "dropped": {}})

    check_eq(quiet["run"]["status"], "quiet",
             "report: a run that read everything and found nothing is 'quiet'")
    check_eq(dead["run"]["status"], "action_needed",
             "report: a run that could not read its sources is 'action_needed'")
    check(quiet["run"]["status_line"] != dead["run"]["status_line"],
          "report: and they do not share a sentence")
    check("NOT because" in dead["run"]["status_line"],
          "report: the broken one says the emptiness is not the news",
          dead["run"]["status_line"])
    check_eq(quiet["run"]["portals_broken"], 0, "report: quiet run, nothing broken")
    check(dead["run"]["portals_broken"] > 0, "report: dead run, everything broken")
    check_eq(quiet["run"]["scanned"], 812,
             "report: a quiet run still says how much it read -- which is what "
             "makes it visibly quiet rather than possibly broken")


def test_a_partial_run_names_itself_as_partial():
    health = fixtures.sample_health()
    payload = _report(health=health)
    check_eq(payload["run"]["status"], "partial",
             "report: one portal down makes the picture incomplete, and says so")
    check(payload["run"]["portals_ok"] < payload["run"]["portals_total"],
          "report: with both numbers, not just a warning")
    check("partial picture" in payload["run"]["status_line"],
          "report: in words as well", payload["run"]["status_line"])


def test_the_status_word_agrees_with_the_filename_and_the_documents():
    """One derivation, not three that can drift apart.

    An app re-deciding "is this a bad run" from the counts would eventually
    disagree with the Word pack, and nobody would see the disagreement.
    """
    cases = [([], fixtures.all_broken_health(), "action_needed", "ACTION-NEEDED"),
             ([], _all_ok(), "quiet", "no-new-opportunities"),
             ([{"score": 1}], fixtures.sample_health(), "partial",
              "portals-unavailable"),
             ([{"score": 1}], _all_ok(), "ok", "1-opportunity")]
    for tenders, health, status, slug_fragment in cases:
        check_eq(reporter.run_status(len(tenders), health), status,
                 f"status: {status} is named as such")
        slug = reporter.run_slug(len(tenders), health)
        check(slug_fragment in slug,
              f"status: the filename slug agrees for {status}", slug)


def test_dropped_counts_survive_so_a_thin_report_is_explicable():
    """"Why is this report so short" is a question the app has to answer."""
    payload = _report()
    dropped = payload["run"]["dropped"]
    check(isinstance(dropped, dict), "report: the filter's reasons are a map")
    check(payload["run"]["scanned"] >= payload["run"]["opportunity_count"],
          "report: more was read than was reported, and both numbers are here")
    check("merged_duplicates" in payload["run"],
          "report: merged duplicates are stated rather than silently missing")


def test_arabic_survives_as_arabic():
    """A notice kept in the original is no use rendered as escape sequences."""
    records = fixtures.sample_records()
    payload = _report(records=records)
    blob = json.dumps(payload, ensure_ascii=False)
    check(any("الأردن" in blob or
              "استشار" in blob
              for _ in [0]),
          "report: Arabic text is carried through in the original script")

    arabic = [t for t in payload["tenders"]
              if (t.get("language") or "").lower().startswith("ar")]
    check(arabic, "report: and an Arabic notice reaches the app at all")
    for tender in arabic:
        check(tender["flags"],
              "report: flagged for manual review, as the report does on paper")


def test_a_run_with_no_result_block_still_writes_a_usable_document():
    """write_json is also reachable from --dry-run and from a test.

    A missing `result` must not produce a document with holes in it: the app
    would render zeroes and there would be nothing to say they were placeholders.
    """
    payload = _write([], fixtures.sample_health())
    check_eq(payload["run"]["scanned"], 0, "report: scanned defaults to 0")
    check_eq(payload["run"]["dropped"], {}, "report: dropped defaults to empty")
    check(payload["run"]["status_line"],
          "report: and the run still describes itself in words")


def test_the_json_format_is_actually_produced_by_a_run():
    """Wiring, not just a function. The app reads a file, not a call."""
    with tempfile.TemporaryDirectory(prefix="jtm-outputs-") as tmp:
        original = list(config.OUTPUT_FORMATS)
        try:
            config.OUTPUT_FORMATS = ["json"]
            result = filters.process(fixtures.sample_records())
            reporter.decorate(result["tenders"])
            written = reporter.write_outputs(result, fixtures.sample_health(),
                                             "<html></html>", Path(tmp))
        finally:
            config.OUTPUT_FORMATS = original

        check("json" in written, "outputs: a run writes the JSON report")
        path = written.get("json")
        if path:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            check_eq(payload["schema"], reporter.REPORT_SCHEMA,
                     "outputs: and it is the versioned document")
            check_eq(payload["run"]["opportunity_count"],
                     len(result["tenders"]),
                     "outputs: carrying the run's own counts, not recomputed ones")
            check("portals-unavailable" in Path(path).name
                  or "opportunit" in Path(path).name,
                  "outputs: the filename still states the run's health",
                  Path(path).name)




def test_every_row_says_which_country_it_is_about():
    """A Jordan sheet and a Syria sheet cannot be stacked if one of them does
    not say which is which.

    The value is constant in this report, and that is the point: it is the
    column that survives a merge. Reports are not merged yet, so nothing here
    depends on that -- this is the field being present and correct before
    anything relies on it.
    """
    record = base.build_record(portal="ted", title="Rehabilitation of clinics",
                               url="https://example.test/1")
    check_eq(record["country"], config.COUNTRY_NAME,
             "every record names the country this monitor is scoped to")


def test_the_source_country_is_kept_rather_than_only_acted_on():
    """TED, the World Bank and SAM.gov each read a country field to decide what
    to keep, and each threw the value away afterwards.

    Three states have to stay distinguishable, because they mean different
    things to a reader deciding whether to open a notice: the source named this
    country, the source named a different one, or the source named none at all.
    Collapsing the last two -- blank and "somewhere else" -- is what makes a
    regional contract look like a local one.
    """
    here = base.build_record(portal="ted", title="Clinic works",
                             url="https://example.test/1", delivery_country="JOR")
    elsewhere = base.build_record(portal="ted", title="Regional programme",
                                  url="https://example.test/2",
                                  delivery_country="Lebanon")
    unstated = base.build_record(portal="fcdo", title="Notice with no country",
                                 url="https://example.test/3")

    check_eq(here["delivery_country"], "JOR", "the source named this country")
    check_eq(elsewhere["delivery_country"], "Lebanon", "the source named another")
    check(unstated["delivery_country"] is None,
          "no country stated is None, not an empty string and not this country")


def test_both_country_columns_reach_the_spreadsheet():
    """The columns are what the request was actually about."""
    labels = [label for _, label in reporter.COLUMNS]
    check("Country" in labels, "the spreadsheet has a Country column")
    check("Delivery country" in labels,
          "and the country the source stated, beside it")

    record = base.build_record(portal="ted", title="Clinic works",
                               url="https://example.test/1", delivery_country="JOR")
    check_eq(reporter._cell(record, "country"), config.COUNTRY_NAME,
             "the cell renders rather than coming out blank")
    check_eq(reporter._cell(record, "delivery_country"), "JOR", "and so does the other")


def test_the_report_schema_is_not_bumped_for_an_added_field():
    """Bumping it would stop every installed app rendering anything.

    The app refuses a schema it was not written for -- deliberately, since half
    parsed nonsense is worse -- and it already ignores keys it does not know.
    So an ADDED field must not bump: the constant means "what the old fields
    mean has changed", and these two are new.
    """
    check_eq(reporter.REPORT_SCHEMA, 1,
             "adding country columns is not a breaking schema change")


def test_the_word_pack_only_names_a_delivery_country_worth_naming():
    """"Delivery country: Jordan" under every entry of a Jordan report is noise;
    a contract delivered in Lebanon is the one thing a reader needs to see.

    Sources write the same place two ways -- TED says JOR, SAM.gov says
    Jordan -- so the comparison cannot be string equality against the name.
    """
    check(reporter._is_this_country("Jordan"), "the name is this country")
    check(reporter._is_this_country("JOR"), "and so is the ISO code TED uses")
    check(reporter._is_this_country("  jo  "), "spacing and case do not matter")
    check(not reporter._is_this_country("Lebanon"), "somewhere else is not")
    check(not reporter._is_this_country(""), "and nothing stated is not either")


TESTS = [
    test_every_row_says_which_country_it_is_about,
    test_the_word_pack_only_names_a_delivery_country_worth_naming,
    test_the_source_country_is_kept_rather_than_only_acted_on,
    test_both_country_columns_reach_the_spreadsheet,
    test_the_report_schema_is_not_bumped_for_an_added_field,
    test_the_app_can_render_every_row_without_guessing,
    test_every_portal_is_in_the_table_in_full,
    test_an_unknown_deadline_is_null_rather_than_an_empty_string,
    test_scanned_stays_null_rather_than_becoming_zero,
    test_a_quiet_run_and_a_broken_run_are_different_documents,
    test_a_partial_run_names_itself_as_partial,
    test_the_status_word_agrees_with_the_filename_and_the_documents,
    test_dropped_counts_survive_so_a_thin_report_is_explicable,
    test_arabic_survives_as_arabic,
    test_a_run_with_no_result_block_still_writes_a_usable_document,
    test_the_json_format_is_actually_produced_by_a_run,
]
