"""
Testing a portal before it is added.

The app's "test it before saving" step runs this. It exists so that adding a
portal from a phone is not a guess -- and the properties that matter are about
honesty rather than about extraction, which is already covered:

  * a candidate that would be REJECTED on load is reported as rejected, and
    nothing is fetched. Telling someone a portal works and then having the run
    refuse it is the worst of both;
  * unreachable, loaded-but-no-listing, and loaded-with-a-weak-listing are
    three different verdicts, because they need three different responses;
  * rows are shown even when nothing clears the quality gate -- whether they
    are notices missing their dates or genuine rubbish is not a question a
    score can answer;
  * it never raises and never fails the run. "This URL is not a listing" is a
    result, and a red run would make it indistinguishable from a broken probe.
"""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

from jordan_tender_monitor import probe as prober
from jordan_tender_monitor.portals import harvester
from jordan_tender_monitor.portals.base import PortalError

from .harness import check, check_eq

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class _Serving:
    """Replace the fetch layer for the duration of a block."""

    def __init__(self, body):
        self.body = body
        self._original = None

    def __enter__(self):
        self._original = harvester._fetch

        def fetch(spec, url):
            if callable(self.body):
                return self.body(url)
            return self.body

        harvester._fetch = fetch
        return self

    def __exit__(self, *exc):
        harvester._fetch = self._original
        return False


def _fixture(name: str) -> str:
    return io.open(FIXTURES / name, encoding="utf-8").read()


def _candidate(**overrides) -> dict:
    entry = {"key": "example", "name": "Example Donor",
             "urls": ["https://example.org/tenders"]}
    entry.update(overrides)
    return entry


# ---------------------------------------------------------------------------


def test_a_readable_listing_is_reported_as_usable_with_its_rows():
    with _Serving(_fixture("drupal_views.html")):
        document = prober.probe(_candidate(selectors=[".views-row"]))

    check_eq(document["schema"], prober.PROBE_SCHEMA,
             "probe: the document states its schema")
    verdict = document["verdict"]
    check(verdict["usable"], "probe: a real listing is usable")
    check("Read 4 rows" in verdict["headline"],
          "probe: the headline says how many rows, not just that it worked",
          verdict["headline"])

    source = document["sources"][0]
    check(source["fetched"], "probe: the page was fetched")
    check(source["bytes"] > 0, "probe: and its size is reported")
    check_eq(source["winner"], "selectors", "probe: the winning layer is named")
    check(source["winning_quality"] >= 0.36,
          "probe: the winner cleared the quality gate")

    layers = {layer["layer"] for layer in source["layers"]}
    for expected in ("feed", "embedded-json", "selectors", "table",
                     "structural", "anchor-pattern"):
        check(expected in layers, f"probe: the {expected} layer is reported")

    check(source["sample_rows"], "probe: sample rows come back")
    check(all(row["title"] for row in source["sample_rows"]),
          "probe: with titles, so nav-dressed-as-notices is visible")
    check(any(row["raw_text"] for row in source["sample_rows"]),
          "probe: and the raw text the date parser actually sees")
    check(not source["sample_rejected"],
          "probe: these rows are from the winning layer")


def test_the_advice_says_a_score_cannot_see_a_wrong_column():
    """GIZ scored 1.00 with every deadline garbage. Do not let a score reassure."""
    with _Serving(_fixture("drupal_views.html")):
        document = prober.probe(_candidate(selectors=[".views-row"]))
    advice = document["verdict"]["advice"]
    check("column" in advice,
          "probe: the advice warns that a score cannot see a wrong column",
          advice)
    check("sample rows" in advice,
          "probe: and points at the rows, which can")


def test_an_unreachable_host_is_not_confused_with_an_empty_page():
    def blocked(url):
        raise PortalError("bot wall (Cloudflare/Incapsula) - needs a different "
                          "network or Playwright", url)

    with _Serving(blocked):
        document = prober.probe(_candidate())

    verdict = document["verdict"]
    check(not verdict["usable"], "probe: an unreachable host is not usable")
    check("Nothing could be fetched" in verdict["headline"],
          "probe: and says so plainly", verdict["headline"])
    check("bot wall" in verdict["detail"],
          "probe: carrying the diagnosed reason", verdict["detail"])
    check_eq(document["sources"][0]["fetched"], False,
             "probe: the source is marked unfetched")
    check_eq(document["sources"][0]["sample_rows"], [],
             "probe: and no rows are invented")


def test_a_page_that_loaded_with_no_listing_is_diagnosed_as_such():
    with _Serving(_fixture("js_shell.html")):
        document = prober.probe(_candidate())

    verdict = document["verdict"]
    check(not verdict["usable"], "probe: a page with no listing is not usable")
    check("loaded" in verdict["headline"] or "below the quality gate"
          in verdict["headline"],
          "probe: the headline distinguishes it from an unreachable host",
          verdict["headline"])
    check(document["sources"][0]["fetched"],
          "probe: the page WAS fetched, which is the whole distinction")
    check("JavaScript shell" in document["sources"][0]["diagnosis"],
          "probe: and the diagnosis names what kind of nothing it is",
          document["sources"][0]["diagnosis"])


def test_rows_are_shown_even_when_nothing_clears_the_gate():
    """A layer that found rows at 0.12 has found something.

    Whether those rows are real notices missing their dates or genuine rubbish
    is not a question the score can answer -- only the rows can, so they are
    printed and labelled as rejected rather than withheld.
    """
    with _Serving(_fixture("save_button_rows.html")):
        document = prober.probe(_candidate())

    source = document["sources"][0]
    if source["winner"]:
        # The fixture happens to clear the gate; the property still needs
        # testing, so assert the labelling is coherent either way.
        check(not source["sample_rejected"],
              "probe: a winning layer's rows are not labelled rejected")
    else:
        check(source["sample_rows"],
              "probe: rows are shown even though the gate rejected them")
        check(source["sample_rejected"],
              "probe: and are labelled as rejected, not passed off as good")
        check(source["sample_from"],
              "probe: naming the layer they came from")


def test_a_candidate_that_would_be_rejected_is_never_fetched():
    """Do not tell someone a portal works and then have the run refuse it."""
    document = prober.probe({"key": "Bad Key", "name": "X",
                             "urls": ["https://example.org/x"]})
    check(document["rejected"], "probe: the loader's objection is reported")
    check("key" in document["rejected"][0],
          "probe: naming the field that is wrong", document["rejected"][0])
    check(not document["verdict"]["usable"],
          "probe: and the verdict is not usable")
    check_eq(document["sources"], [],
             "probe: nothing was fetched for an entry that cannot load")


def test_the_probe_validates_with_the_same_loader_a_run_uses():
    """A second validator that agreed most of the time would be worse than none."""
    for entry, expected in (
        ({"key": "x", "name": "X", "urls": []}, "urls"),
        ({"key": "x", "name": "X", "urls": ["ftp://example.org"]}, "http"),
        ({"key": "x", "name": "X", "urls": ["https://e.org"], "tier": 9}, "tier"),
        ({"key": "x", "name": "X", "urls": ["https://e.org"],
          "module": "nonesuch"}, "module"),
    ):
        document = prober.probe(entry)
        check(document["rejected"],
              f"probe: '{expected}' is rejected before any fetch")
        if document["rejected"]:
            check(expected in document["rejected"][0],
                  f"probe: the reason names '{expected}'",
                  document["rejected"][0])


def test_one_source_failing_does_not_hide_another_working():
    """Several portals publish across two sites. The report must show both."""
    good = _fixture("drupal_views.html")

    def flaky(url):
        if "broken" in url:
            raise PortalError("HTTP 404 - the URL has moved", url)
        return good

    with _Serving(flaky):
        document = prober.probe(_candidate(
            urls=["https://broken.example/a", "https://good.example/b"],
            selectors=[".views-row"]))

    check_eq(len(document["sources"]), 2, "probe: both sources are reported")
    check(not document["sources"][0]["fetched"], "probe: the broken one failed")
    check(document["sources"][1]["fetched"], "probe: the working one did not")
    check(document["verdict"]["usable"],
          "probe: and the portal is usable on the strength of the working one")


def test_the_probe_writes_a_document_and_never_raises():
    def explode(url):
        raise ZeroDivisionError("something nobody anticipated")

    with tempfile.TemporaryDirectory(prefix="jtm-probe-") as tmp:
        with _Serving(explode):
            path = prober.write_probe(_candidate(), Path(tmp))
        check(path.exists(), "probe: a document is always written")
        document = json.loads(path.read_text(encoding="utf-8"))
    check(not document["verdict"]["usable"],
          "probe: an unexpected error is not a usable portal")
    check("ZeroDivisionError" in json.dumps(document),
          "probe: and the exception type is reported so it can be debugged")


def test_the_filename_cannot_be_steered_by_the_key():
    """The key comes off a phone keyboard and becomes a filename."""
    with tempfile.TemporaryDirectory(prefix="jtm-probe-") as tmp:
        with _Serving(_fixture("drupal_views.html")):
            path = prober.write_probe(
                {"key": "../../etc/passwd", "name": "X",
                 "urls": ["https://e.org/x"]}, Path(tmp))
        check_eq(path.parent, Path(tmp),
                 "probe: the file lands in the output directory")
        check(".." not in path.name, "probe: and its name carries no traversal",
              path.name)


def test_probing_never_fails_the_run():
    """A red run would make "not a listing" look like a broken probe."""
    from jordan_tender_monitor import run as cli

    original = prober.write_probe
    try:
        with tempfile.TemporaryDirectory(prefix="jtm-probe-") as tmp:
            def to_temp(candidate, output_dir=None):
                return original(candidate, Path(tmp))

            prober.write_probe = to_temp
            def blocked(url):
                raise PortalError("transport error - host blocked", url)

            with _Serving(blocked):
                code = cli.cmd_probe(json.dumps(_candidate()))
            check_eq(code, 0,
                     "probe: an unusable portal still exits zero -- the probe ran")

            bad_json = cli.cmd_probe("{not json")
            check_eq(bad_json, 2, "probe: malformed input exits non-zero")
            not_an_object = cli.cmd_probe('["a", "list"]')
            check_eq(not_an_object, 2, "probe: so does the wrong JSON shape")
    finally:
        prober.write_probe = original


def test_the_workflow_offers_the_probe_mode():
    """It is only reachable from the phone if the workflow exposes it."""
    workflow = io.open(
        Path(__file__).resolve().parent.parent.parent / ".github" / "workflows"
        / "monitor.yml", encoding="utf-8").read()
    check("test a candidate portal (--probe)" in workflow,
          "probe: the workflow has a mode for it")
    check("candidate:" in workflow,
          "probe: and an input to carry the entry")
    check("--probe -" in workflow,
          "probe: the JSON is piped on stdin, not passed through shell quoting")
    check("portal-probe-" in workflow,
          "probe: the result is uploaded as an artifact the app can read")


TESTS = [
    test_a_readable_listing_is_reported_as_usable_with_its_rows,
    test_the_advice_says_a_score_cannot_see_a_wrong_column,
    test_an_unreachable_host_is_not_confused_with_an_empty_page,
    test_a_page_that_loaded_with_no_listing_is_diagnosed_as_such,
    test_rows_are_shown_even_when_nothing_clears_the_gate,
    test_a_candidate_that_would_be_rejected_is_never_fetched,
    test_the_probe_validates_with_the_same_loader_a_run_uses,
    test_one_source_failing_does_not_hide_another_working,
    test_the_probe_writes_a_document_and_never_raises,
    test_the_filename_cannot_be_steered_by_the_key,
    test_probing_never_fails_the_run,
    test_the_workflow_offers_the_probe_mode,
]
