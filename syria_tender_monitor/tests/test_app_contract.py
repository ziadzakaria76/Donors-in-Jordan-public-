"""The Android app dispatches this workflow. These are the two sides agreeing.

The app in `android/` was written for the Jordan monitor and sends one fixed
vocabulary of workflow inputs, whichever workflow file its Settings name. This
project shipped a workflow declaring different ones, so pointing the app here
answered

    422  Unexpected inputs provided: ["scope"]

before a step ran -- a failure with no log to read, because no run was created.
Jordan's suite has had a test for exactly this since the app was built
(test_app_contract.py::test_the_apps_workflow_inputs_match_the_workflow); this
project had no equivalent, so nothing failed until a phone did.

Two things are checked, and they fail differently:

  * every input NAME the app sends is declared -- an undeclared one is the 422;
  * every literal the app sends for a `type: choice` input is an option --
    choice values are matched as exact strings, so `mode: "produce the report"`
    against options `[run, dry-run]` is the same 422 for a subtler reason.

The app is read as source rather than restated here on purpose. A copy of the
strings would agree with itself forever while the app moved on.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "android" / "app" / "src" / "main" / "java" / "jo" / "tendermonitor"
WORKFLOW = REPO / ".github" / "workflows" / "syria-monitor.yml"

pytestmark = pytest.mark.skipif(
    not APP.exists(),
    reason="the Android app is not present in this checkout",
)


def _source(*parts: str) -> str:
    return APP.joinpath(*parts).read_text(encoding="utf-8")


def _workflow_inputs() -> dict:
    """The workflow's declared inputs, for tests that are not fixture-scoped."""
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))[True]["workflow_dispatch"]["inputs"]

@pytest.fixture(scope="module")
def workflow() -> dict:
    # `on:` is parsed by PyYAML as the boolean True (YAML 1.1 keeps "on" as a
    # truthy word), which is why this is not spelled workflow["on"].
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))[True]["workflow_dispatch"]


@pytest.fixture(scope="module")
def app_sources() -> str:
    return (_source("ui", "screens", "RunScreen.kt")
            + _source("ui", "AppViewModel.kt")
            + _source("data", "portals", "PortalsRepository.kt"))


def test_every_input_the_app_sends_is_declared(workflow, app_sources):
    """An input the workflow does not declare is rejected outright."""
    # Two spellings because the app builds one map with buildMap { put(...) }
    # and the other as mapOf("x" to y).
    sent = set(re.findall(r'put\("(\w+)"', app_sources))
    sent |= set(re.findall(r'"(\w+)" to ', app_sources))

    assert {"scope", "mode", "portals", "candidate"} <= sent, (
        "the app's dispatch inputs were not found in its source -- this test "
        f"reads them by pattern and got {sorted(sent)}"
    )

    declared = set(workflow["inputs"])
    assert not sent - declared, (
        f"undeclared inputs: {sorted(sent - declared)}; "
        f"declared: {sorted(declared)}"
    )


def test_every_choice_the_app_sends_is_an_option(workflow, app_sources):
    """A choice input is matched literally: a near-miss is a 422, not a default."""
    scopes = re.findall(r'const val SCOPE_\w+ = "([^"]+)"', app_sources)
    modes = re.findall(r'const val MODE_\w+ = "([^"]+)"', app_sources)
    modes += re.findall(r'const val PROBE_MODE = "([^"]+)"', app_sources)

    assert len(scopes) == 2 and len(modes) == 3, (
        f"expected the app's 2 scopes and 3 modes, got {scopes} and {modes}"
    )

    for value in scopes:
        assert value in workflow["inputs"]["scope"]["options"]
    for value in modes:
        assert value in workflow["inputs"]["mode"]["options"]


def test_the_workflow_acts_on_each_mode_rather_than_defaulting(workflow):
    """Declaring an option is not handling it.

    Both non-report modes need their own branch. Falling through to the
    catch-all would run a full scrape while the app showed the user "diagnose"
    or "test a candidate portal" -- a run that succeeds having done something
    else is worse than one that fails.
    """
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["run"]["steps"]
    script = [s for s in steps if s.get("name") == "Run monitor"][0]["run"]

    assert '"diagnose portals (--capture)")' in script
    assert '"test a candidate portal (--probe)")' in script

    # This monitor has no --probe. The branch has to fail, not fall through.
    probe = script.split('"test a candidate portal (--probe)")', 1)[1].split(";;", 1)[0]
    assert "::error::" in probe and "exit 1" in probe


def test_free_text_inputs_reach_the_shell_as_values(workflow):
    """`portals` and `candidate` are typed by a person and must not be interpolated.

    `${{ inputs.portals }}` inside `run:` pastes the text into the script before
    bash parses it. Through `env:` it stays one value however it is spelled.
    """
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["run"]["steps"]
    step = [s for s in steps if s.get("name") == "Run monitor"][0]

    for name in ("portals", "candidate"):
        assert f"inputs.{name} }}}}" not in step["run"], (
            f"inputs.{name} is interpolated directly into the script"
        )


def test_the_documented_workflow_modes_are_modes_the_workflow_offers():
    """A runbook step that names a mode which no longer exists is a dead end.

    `type: choice` is matched as an exact string, so a documented value that has
    drifted does not degrade -- it is rejected, or silently falls through to the
    default and does something else.

    This is the same drift that produced the 422, one layer out: when the inputs
    were changed to the app's vocabulary, RUNBOOK.md still told the reader to
    pick mode `capture` with portal `all`. Neither had existed since. Someone
    following the setup guide would have got a rejected dispatch and no clue why.
    """
    options = set(_workflow_inputs()["mode"]["options"])
    docs = [REPO / "syria_tender_monitor" / "docs" / "RUNBOOK.md",
            REPO / "syria_tender_monitor" / "README.md",
            REPO / "README.md"]

    documented = []
    for doc in docs:
        if doc.is_file():
            documented += [(doc.name, m) for m in
                           re.findall(r"mode `([^`]+)`", doc.read_text(encoding="utf-8"))]

    for name, mode in documented:
        assert mode in options, (
            f"{name} tells the reader to pick mode {mode!r}, which "
            f"syria-monitor.yml does not offer. Its choices are {sorted(options)}"
        )


# ---------------------------------------------------------------------------
# The report JSON the app actually parses
# ---------------------------------------------------------------------------
#
# THE BRIDGE WRITER HAD NO CONTRACT TEST AT ALL. app_json_writer.py is the only
# thing feeding the Android app on a Syria run, and nothing checked it against
# the app's parser. Jordan has had that check since the app was built; this
# project shipped the writer without one, which is the same gap that let the
# workflow inputs drift into a 422 and the artifact name drift into a Files tab
# that refused a good run.
#
# A drift here is quiet in the worst way: kotlinx is configured with
# ignoreUnknownKeys, so a renamed key does not throw -- the app reads the
# property's default instead and renders a confident, wrong screen.

_KOTLIN_PROPERTY = re.compile(
    r"^\s*(?:@SerialName\(\"(?P<serial>[^\"]+)\"\)\s*)?"
    r"val\s+(?P<name>\w+)\s*:\s*(?P<type>[\w<>?.]+)"
    r"(?P<default>\s*=)?",
    re.M,
)


def _kotlin_properties(source: str, class_name: str) -> list[tuple[str, str]]:
    """(json key, kotlin type) for one data class's constructor properties."""
    start = source.index(f"data class {class_name}(")
    depth, end = 0, start
    for i in range(source.index("(", start), len(source)):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    body = source[start:end]
    out = []
    for m in _KOTLIN_PROPERTY.finditer(body):
        # `val x: T get() = ...` is computed, not serialised, and has no default
        # marker; constructor properties are the ones that come from JSON.
        if "get()" in body[m.end():m.end() + 12]:
            continue
        out.append((m.group("serial") or m.group("name"), m.group("type")))
    return out


def _type_fits(value, kotlin_type: str) -> bool:
    optional = kotlin_type.endswith("?")
    base = kotlin_type.rstrip("?")
    if value is None:
        return optional
    if base.startswith("List<"):
        return isinstance(value, list)
    if base == "String":
        return isinstance(value, str)
    if base in ("Int", "Long"):
        return isinstance(value, int) and not isinstance(value, bool)
    if base == "Double":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if base == "Boolean":
        return isinstance(value, bool)
    return True          # a nested data class; checked by its own pass


def _syria_app_document(tmp_path) -> dict:
    """A real document from the real writer, over the real pipeline."""
    import json
    import yaml
    from syria_monitor.config import Config
    from syria_monitor.fetch import Fetcher
    from syria_monitor.pipeline import run as run_pipeline
    from syria_monitor.portals import REGISTRY
    from syria_monitor.portals.base import BasePortal
    from syria_monitor.report import write_app_json

    root = REPO / "syria_tender_monitor"
    profile = yaml.safe_load((root / "profiles" / "syria.yml").read_text(encoding="utf-8"))
    data = yaml.safe_load((root / "config.yml").read_text(encoding="utf-8"))
    data["state"]["db_path"] = str(tmp_path / "seen.db")
    data["output"]["dir"] = str(tmp_path / "out")
    cfg = Config(data, profile)

    def portal(name, records, fails=False, skip=None):
        class Fake(BasePortal):
            pass
        Fake.name, Fake.label, Fake.url = name, name.upper(), f"https://{name}.example"
        Fake.fetch_tenders = lambda self: (_ for _ in ()).throw(RuntimeError("boom")) \
            if fails else records
        Fake.unavailable_reason = lambda self: skip
        return Fake

    record = {"id": "1", "title": "Rehabilitation of the Aleppo water network",
              "project_ctry_name": "Syrian Arab Republic",
              "closing_date": "2099-09-30", "_safe_text_fields": ["title"]}

    original = dict(REGISTRY)
    try:
        REGISTRY.clear()
        # THE THREE STATES THE APP HAS TO RENDER, not just the happy one: a
        # portal that worked, one that failed, and one skipped for a missing
        # key. The last two are where the writer emits nulls.
        REGISTRY["ok"] = portal("ok", [record])
        REGISTRY["broken"] = portal("broken", [], fails=True)
        REGISTRY["skipped"] = portal("skipped", [], skip="NO_KEY not set")
        result = run_pipeline(cfg, fetcher=Fetcher(),
                              portals=["ok", "broken", "skipped"])
    finally:
        REGISTRY.clear()
        REGISTRY.update(original)

    path = write_app_json(result, tmp_path / "app.json", cfg.profile)
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_app_reads_every_field_the_syria_writer_writes(tmp_path):
    """Every constructor property of the app's model must be present and fit."""
    source = (APP / "data" / "report" / "Report.kt").read_text(encoding="utf-8")
    doc = _syria_app_document(tmp_path)

    def check_class(class_name, payload, label):
        props = _kotlin_properties(source, class_name)
        assert props, f"no properties parsed from {class_name}"
        for key, ktype in props:
            assert key in payload, (
                f"{label} is missing '{key}' for {class_name}.{key} — the app "
                f"would read a default and render it as fact. Document has: "
                f"{sorted(payload)}"
            )
            assert _type_fits(payload[key], ktype), (
                f"{label}['{key}'] = {payload[key]!r} does not fit {ktype}"
            )

    check_class("Report", doc, "the Syria report")
    check_class("RunSummary", doc["run"], "its run block")

    assert doc["tenders"], "the fixture run produced no opportunity to check"
    for tender in doc["tenders"]:
        check_class("Opportunity", tender, "an opportunity")

    assert doc["portals"], "the fixture run produced no portal row to check"
    for portal in doc["portals"]:
        check_class("PortalStatus", portal, "a portal status")


def test_the_schema_constant_matches_on_both_sides(tmp_path):
    """A schema the app refuses is a blank screen, whatever the run found."""
    # SUPPORTED_SCHEMA lives in Report.kt; ReportParser.kt only compares against
    # it. Reading the parser instead matches its `schema == 0` guard and 
    # "supports 0" -- which is how the first draft of this test failed.
    model = (APP / "data" / "report" / "Report.kt").read_text(encoding="utf-8")
    found = re.search(r"SUPPORTED_SCHEMA\s*(?::\s*Int\s*)?=\s*(\d+)", model)
    assert found, "no SUPPORTED_SCHEMA constant found in Report.kt"
    supported = int(found.group(1))

    written = _syria_app_document(tmp_path)["schema"]
    # The parser refuses anything NEWER than it understands, and treats 0 as a
    # document with no version at all.
    assert written != 0, "a schema of 0 is read as 'no version' and refused"
    assert written <= supported, (
        f"Syria writes schema {written}; this app understands {supported}, and "
        f"ReportParser refuses anything newer -- every installed build would "
        f"show 'the app is out of date' on an otherwise good run"
    )


def test_a_skipped_or_broken_portal_reports_null_scanned_not_zero(tmp_path):
    """Null and 0 mean different things, and the app renders them differently.

    A portal that was never polled has no count; a portal that read nothing has
    a count of zero. Collapsing them tells the reader a broken portal looked and
    found nothing.
    """
    doc = _syria_app_document(tmp_path)
    by_key = {p["key"]: p for p in doc["portals"]}

    assert by_key["ok"]["scanned"] is not None
    assert by_key["broken"]["scanned"] is None, "an unreachable portal must not claim 0"
    assert by_key["skipped"]["scanned"] is None, "an unpolled portal must not claim 0"
    assert by_key["skipped"]["status"] == "unconfigured"
    assert by_key["broken"]["status"] == "unavailable"
