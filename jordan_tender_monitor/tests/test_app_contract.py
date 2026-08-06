"""
The Python documents and the Kotlin models that read them, checked against
each other.

THIS IS THE ONE SEAM NOTHING ELSE COVERS. The Python tests prove the report and
the probe document are written correctly. The Kotlin tests prove the app parses
documents *the Kotlin tests themselves wrote*. Neither notices when the two
drift apart -- and kotlinx.serialization is built to not notice either: every
field has a default, so a renamed or removed key does not fail, it silently
becomes 0, "" or null.

That is the exact failure this codebase keeps finding in other clothes. A
portal's `scanned` quietly becoming 0. A deadline quietly becoming "no
deadline". The app would render a plausible, wrong, complete-looking screen and
nothing anywhere would say so.

So this reads the Kotlin data classes as text, works out which JSON key each
property expects, and checks a REAL document produced by the pipeline actually
carries it, with a compatible type. It is not a substitute for compiling the
app -- it is the check that compiling the app cannot do.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from jordan_tender_monitor import config, fixtures, probe as prober
from jordan_tender_monitor.agents import filter as filters, reporter
from jordan_tender_monitor.portals import base, harvester

from .harness import check, check_eq

APP = (Path(__file__).resolve().parent.parent.parent / "android" / "app" / "src"
       / "main" / "java" / "jo" / "tendermonitor")

# `@SerialName("x") val y: T = default` or `val y: T = default`.
_PROPERTY = re.compile(
    r'(?:@SerialName\("(?P<serial>[^"]+)"\)\s*)?'
    r'val\s+(?P<name>\w+)\s*:\s*(?P<type>[A-Za-z0-9_<>?, .]+?)\s*=',
)

_CLASS = re.compile(r'data class (?P<name>\w+)\s*\(', re.M)


def _kotlin_properties(source: str, class_name: str) -> list[tuple[str, str]]:
    """(json key, kotlin type) for one data class's constructor."""
    match = re.search(rf'data class {class_name}\s*\(', source)
    if not match:
        return []
    # Walk to the matching close paren so a nested generic or default cannot
    # end the scan early.
    depth, index = 0, match.end() - 1
    while index < len(source):
        if source[index] == "(":
            depth += 1
        elif source[index] == ")":
            depth -= 1
            if depth == 0:
                break
        index += 1
    body = source[match.end():index]

    out = []
    for prop in _PROPERTY.finditer(body):
        key = prop.group("serial") or prop.group("name")
        out.append((key, prop.group("type").strip()))
    return out


def _kotlin_block(source: str, header: str) -> str:
    """The brace-balanced body that follows `header` in `source`.

    Used to scan one function rather than a whole file, so a document-level
    key like `portals` written by an unrelated function is not mistaken for a
    field of a portal entry.
    """
    start = source.index(header) + len(header)
    open_brace = source.index("{", start)
    depth, index = 0, open_brace
    while index < len(source):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace + 1:index]
        index += 1
    raise AssertionError(f"unbalanced braces after {header!r}")


def _type_ok(value, kotlin_type: str) -> bool:
    """Whether a JSON value can be read as the declared Kotlin type."""
    nullable = kotlin_type.endswith("?")
    base = kotlin_type.rstrip("?").strip()

    if value is None:
        return nullable

    if base == "String":
        return isinstance(value, str)
    if base == "Int":
        return isinstance(value, int) and not isinstance(value, bool)
    if base == "Long":
        return isinstance(value, int) and not isinstance(value, bool)
    if base == "Double":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if base == "Boolean":
        return isinstance(value, bool)
    if base.startswith("List<"):
        return isinstance(value, list)
    if base.startswith("Map<"):
        return isinstance(value, dict)
    # A nested data class.
    return isinstance(value, dict)


def _check_class(source: str, class_name: str, payload: dict, label: str) -> None:
    properties = _kotlin_properties(source, class_name)
    check(bool(properties),
          f"contract: {class_name} was found and parsed",
          f"no properties read from {class_name}")

    for key, kotlin_type in properties:
        present = key in payload
        check(present,
              f"contract: {label} carries '{key}' for {class_name}.{key}",
              f"the app would silently read a default. Document has: "
              f"{sorted(payload)[:12]}")
        if present:
            check(_type_ok(payload[key], kotlin_type),
                  f"contract: {label}['{key}'] fits {kotlin_type}",
                  f"got {payload[key]!r}")


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def _report_document(records=None, health=None) -> dict:
    records = fixtures.sample_records() if records is None else records
    health = fixtures.sample_health() if health is None else health
    result = filters.process(records)
    reporter.decorate(result["tenders"])
    with tempfile.TemporaryDirectory(prefix="jtm-contract-") as tmp:
        path = Path(tmp) / "report.json"
        reporter.write_json(result["tenders"], health, path, result)
        return json.loads(path.read_text(encoding="utf-8"))


def test_the_app_reads_every_field_the_report_writes():
    source = (APP / "data" / "report" / "Report.kt").read_text(encoding="utf-8")
    document = _report_document()

    _check_class(source, "Report", document, "the report")
    _check_class(source, "RunSummary", document["run"], "the report's run block")

    check(document["tenders"], "contract: there is an opportunity to check")
    for tender in document["tenders"]:
        _check_class(source, "Opportunity", tender, "an opportunity")

    check(document["portals"], "contract: there is a portal to check")
    for portal in document["portals"]:
        _check_class(source, "PortalStatus", portal, "a portal status")


def test_the_app_reads_a_report_from_a_run_that_found_nothing():
    """Empty and broken have to stay distinguishable all the way to the screen.

    A run that found nothing is a normal morning. A run where every portal was
    unreachable is an emergency. Both produce a report with no opportunities in
    it, so the difference lives entirely in the run block and the portal
    statuses -- and if a field goes missing on this path it defaults to 0, the
    counts read as a quiet day, and the app renders the emergency as the normal
    morning.
    """
    source = (APP / "data" / "report" / "Report.kt").read_text(encoding="utf-8")
    broken = [h for h in fixtures.sample_health() if h.status != "ok"]
    check(broken, "contract: the fixture has an unavailable portal to use")

    document = _report_document(records=[], health=broken)

    _check_class(source, "Report", document, "an empty report")
    _check_class(source, "RunSummary", document["run"], "an empty report's run block")
    for portal in document["portals"]:
        _check_class(source, "PortalStatus", portal, "a portal status (empty run)")

    check_eq(document["tender_count"], 0,
             "contract: an empty report says so with a count, not an absent key")
    check_eq(document["run"]["portals_ok"], 0,
             "contract: and reports no portal read successfully")
    check(document["run"]["portals_broken"] > 0,
          "contract: and reports the broken ones as broken",
          f"got {document['run']['portals_broken']}")
    check(document["run"]["status"] != "ok",
          "contract: so the run status is not 'ok' -- which is the whole "
          "difference between a quiet day and an outage",
          f"got {document['run']['status']!r}")
    check(document["run"]["status_line"],
          "contract: with a line that says which of the two it was")


def test_the_report_schema_constant_matches_on_both_sides():
    """A mismatch here means the app refuses every report, or accepts a wrong one."""
    source = (APP / "data" / "report" / "Report.kt").read_text(encoding="utf-8")
    match = re.search(r"SUPPORTED_SCHEMA\s*=\s*(\d+)", source)
    check(match is not None, "contract: the app declares a supported schema")
    if match:
        check_eq(int(match.group(1)), reporter.REPORT_SCHEMA,
                 "contract: the app's supported schema is the one the pipeline writes")


# ---------------------------------------------------------------------------
# The probe document
# ---------------------------------------------------------------------------


def _probe_document(fetch) -> dict:
    original = harvester._fetch
    try:
        harvester._fetch = fetch
        return prober.probe({
            "key": "example", "name": "Example Donor",
            "urls": ["https://example.org/tenders"],
            "selectors": [".views-row"],
        })
    finally:
        harvester._fetch = original


def _reads_well(spec, url):
    return (Path(__file__).resolve().parent / "fixtures" / "drupal_views.html"
            ).read_text(encoding="utf-8")


def _cannot_be_reached(spec, url):
    raise base.PortalError("transport error - the host is blocked")


def _check_probe_document(document, label: str) -> None:
    source = (APP / "data" / "portals" / "ProbeReport.kt").read_text(encoding="utf-8")

    _check_class(source, "ProbeReport", document, f"the probe document ({label})")
    _check_class(source, "ProbeVerdict", document["verdict"],
                 f"the probe verdict ({label})")

    check(document["sources"], f"contract: the probe reports a source ({label})")
    for source_result in document["sources"]:
        _check_class(source, "ProbeSource", source_result, f"a probe source ({label})")
        for layer in source_result["layers"]:
            _check_class(source, "ProbeLayer", layer, f"a probe layer ({label})")
        for row in source_result["sample_rows"]:
            _check_class(source, "ProbeRow", row, f"a probe sample row ({label})")


def test_the_app_reads_every_field_the_probe_writes():
    _check_probe_document(_probe_document(_reads_well), "usable")


def test_the_app_reads_a_probe_that_could_not_read_anything():
    """The failure document is the one the app is most likely to meet first.

    Someone testing a URL they have just typed is more likely to have got it
    wrong than right. If the writer skips fields on that path, every one of
    them arrives in the app as 0 or "" -- and the screen reports a portal that
    found no rows rather than one that could not be reached at all.
    """
    document = _probe_document(_cannot_be_reached)
    _check_probe_document(document, "unreachable")

    source = document["sources"][0]
    check(not source["fetched"], "contract: the failed source says it was not fetched")
    check(source["error"], "contract: and carries a reason, not an empty string")
    check(not document["verdict"]["usable"],
          "contract: the verdict on an unreachable candidate is not usable")
    check(document["verdict"]["headline"],
          "contract: with a headline, so the screen is never blank")


def test_the_probe_schema_constant_matches_on_both_sides():
    source = (APP / "data" / "portals" / "ProbeReport.kt").read_text(encoding="utf-8")
    match = re.search(r"SUPPORTED_SCHEMA\s*=\s*(\d+)", source)
    check(match is not None, "contract: the app declares a supported probe schema")
    if match:
        check_eq(int(match.group(1)), prober.PROBE_SCHEMA,
                 "contract: and it is the one --probe writes")


# ---------------------------------------------------------------------------
# The portal file, and the workflow inputs
# ---------------------------------------------------------------------------


def test_the_app_reads_the_portal_fields_the_loader_accepts():
    """Every field the app writes must be one portal_config.py will accept.

    An app that wrote a field the loader rejects would produce a commit that
    breaks the next run -- from a screen that had just said "Committed".
    """
    from jordan_tender_monitor import portal_config

    source = (APP / "data" / "portals" / "PortalsFile.kt").read_text(encoding="utf-8")
    # Only the entry builder: elsewhere the file writes the document-level
    # `portals` array, which is not a field of an entry.
    builder = _kotlin_block(source, "): JsonObject = buildJsonObject")
    written = set(re.findall(r'put\("([a-z_]+)"', builder))
    check(written, "contract: the app's entry builder was parsed",
          f"found {written}")
    check_eq(written, {"key", "name", "enabled", "tier", "urls", "selectors",
                       "anchor_hint", "currency", "filter_to_jordan", "notes"},
             "contract: the entry builder writes the fields the Add form collects")

    unknown = sorted(written - portal_config._ALLOWED_KEYS)
    check(not unknown,
          "contract: every field the app writes is one the loader accepts",
          f"the loader would reject: {unknown}")

    # And the reverse direction for the fields it displays.
    read = set(re.findall(r'stringOf\("([a-z_]+)"\)', source)) \
        | set(re.findall(r'stringsOf\("([a-z_]+)"\)', source)) \
        | set(re.findall(r'boolOf\("([a-z_]+)"', source)) \
        | set(re.findall(r'intOf\("([a-z_]+)"', source))
    unknown_read = sorted(read - portal_config._ALLOWED_KEYS)
    check(not unknown_read,
          "contract: and every field it reads is one the file can contain",
          f"never present: {unknown_read}")

    check_eq(re.search(r'const val PATH = "([^"]+)"', source).group(1),
             "jordan_tender_monitor/portals.json",
             "contract: the app commits to the path the loader reads")


def test_the_forms_rules_are_the_rules_the_loader_enforces():
    """The Add form rejects early so a bad entry never becomes a commit.

    If its rules are looser than the loader's, the form says yes, the commit
    lands, and the portal is silently dropped on the next run -- from a screen
    that had just said "Committed". If they are tighter, it refuses entries
    that would have worked. Either way the two have to agree, and nothing else
    checks that they do.
    """
    from jordan_tender_monitor import portal_config

    source = (APP / "data" / "portals" / "PortalsFile.kt").read_text(encoding="utf-8")

    kotlin_key = re.search(r'val KEY = Regex\("([^"]+)"\)', source)
    check(kotlin_key is not None, "contract: the form's key rule was found")
    if kotlin_key:
        check_eq(kotlin_key.group(1), portal_config.KEY_RE.pattern,
                 "contract: the form's key rule is the loader's key rule")

    # Exercised rather than compared as text: a regex can be spelled two ways.
    for candidate, allowed in (("undp", True), ("world-bank_2", True),
                               ("_leading", False), ("Upper", False),
                               ("has space", False), ("", False),
                               ("x" * 40, True), ("x" * 41, False)):
        check_eq(bool(portal_config.KEY_RE.match(candidate)), allowed,
                 f"contract: the loader treats {candidate[:12]!r} as "
                 f"{'valid' if allowed else 'invalid'}")

    tiers = re.search(r'if \(tier in (\d)\.\.(\d)\)', source)
    check(tiers is not None, "contract: the form's tier rule was found")
    if tiers:
        allowed_by_form = set(range(int(tiers.group(1)), int(tiers.group(2)) + 1))
        allowed_by_loader = set()
        for tier in range(0, 6):
            entry = {"key": "probe_tier", "name": "T", "tier": tier,
                     "urls": ["https://example.org/x"]}
            definition, _problem = portal_config._validate(entry, 0, set())
            if definition is not None:
                allowed_by_loader.add(tier)
        check_eq(allowed_by_form, allowed_by_loader,
                 "contract: the form accepts exactly the tiers the loader does")


def test_the_app_can_find_the_files_the_run_actually_produces():
    """The app picks files out of the artifact zip by name. Names drift.

    Every one of these is a bare string on the Kotlin side matched against a
    filename generated on the Python side, with a CI artifact in between. If
    one stops matching, the app does not fail -- it reports an artifact with no
    report in it, which reads exactly like a run that produced nothing.
    """
    import io

    source = (APP / "data" / "report" / "ArtifactZip.kt").read_text(encoding="utf-8")
    marker = re.search(r'name\.contains\("([^"]+)"\)', source)
    check(marker is not None, "contract: the app's report-file marker was found")

    workflow = io.open(
        Path(__file__).resolve().parent.parent.parent / ".github" / "workflows"
        / "monitor.yml", encoding="utf-8").read()

    # The JSON report exists ONLY because the workflow asks for it -- the
    # default is docx and excel. So take the formats from the workflow and
    # write with them, rather than testing a configuration CI does not use.
    #
    # Parsed rather than grepped: monitor.yml sets JTM_OUTPUT_FORMATS twice,
    # and the first one belongs to the diagnose step, which writes markdown
    # only. A regex for the first match would have tested the wrong step and
    # passed while the real one wrote no json at all.
    import yaml

    steps = yaml.safe_load(workflow)["jobs"]["monitor"]["steps"]
    running = [s for s in steps if "--run" in str(s.get("run", ""))]
    check(len(running) == 1,
          "contract: exactly one step runs the monitor",
          f"found {[s.get('name') for s in running]}")
    formats = [f.strip() for f in
               running[0].get("env", {}).get("JTM_OUTPUT_FORMATS", "").split(",")
               if f.strip()]
    check(formats,
          "contract: the step that runs the monitor states its output formats")
    check("json" in formats,
          "contract: and asks for json, which is the only file the app reads",
          f"it asks for {formats}")

    original = config.OUTPUT_FORMATS
    try:
        config.OUTPUT_FORMATS = formats
        with tempfile.TemporaryDirectory(prefix="jtm-names-") as tmp:
            records = fixtures.sample_records()
            health = fixtures.sample_health()
            result = filters.process(records)
            reporter.decorate(result["tenders"])
            written = reporter.write_outputs(result, health, "<html></html>",
                                             Path(tmp))
    finally:
        config.OUTPUT_FORMATS = original

    check("json" in written,
          "contract: and the run really writes it with those formats",
          f"wrote {sorted(written)}")
    if marker and "json" in written:
        check(marker.group(1) in written["json"].name,
              f"contract: the app finds {written['json'].name} by "
              f"{marker.group(1)!r}")

    # The extensions, against the real files rather than against a convention.
    for kind, extension in (("docx", ".docx"), ("excel", ".xlsx")):
        if kind in written:
            check(f'endsWith("{extension}"' in source,
                  f"contract: the app recognises {extension}, which the run writes")
            check(written[kind].name.endswith(extension),
                  f"contract: and the run really writes {extension}")

    # And the workflow has to upload all three, or the app finds an artifact
    # that is missing exactly the file it came for.
    for extension in (".docx", ".xlsx", ".json"):
        check(f"output/*{extension}" in workflow,
              f"contract: monitor.yml uploads {extension} files")

    # One level up: the app picks the ARTIFACT by name before it opens the zip
    # at all. Both prefixes are bare strings on each side, and a run's artifact
    # list contains more than one artifact, so a stale prefix does not fail --
    # it selects nothing, or the wrong one.
    uploads = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    published = [s.get("with", {}).get("name", "") for s in uploads]
    check(published, "contract: monitor.yml uploads at least one artifact")

    repository = (APP / "data" / "ReportRepository.kt").read_text(encoding="utf-8")
    portals_repo = (APP / "data" / "portals" / "PortalsRepository.kt").read_text(
        encoding="utf-8")

    for label, source_text, pattern in (
        ("the report", repository, r'name\.startsWith\("([^"]+)"\)'),
        ("the probe", portals_repo, r'name\.startsWith\("([^"]+)"\)'),
    ):
        prefix = re.search(pattern, source_text)
        check(prefix is not None,
              f"contract: the artifact prefix the app uses for {label} was found")
        if prefix:
            check(any(name.startswith(prefix.group(1)) for name in published),
                  f"contract: an artifact for {label} really starts with "
                  f"{prefix.group(1)!r}",
                  f"monitor.yml publishes {published}")


def test_the_apps_workflow_inputs_match_the_workflow():
    """A choice input is matched literally. A typo is a 422 at the moment you tap Run."""
    import io

    workflow = io.open(
        Path(__file__).resolve().parent.parent.parent / ".github" / "workflows"
        / "monitor.yml", encoding="utf-8").read()

    run_screen = (APP / "ui" / "screens" / "RunScreen.kt").read_text(encoding="utf-8")
    repository = (APP / "data" / "portals" / "PortalsRepository.kt").read_text(
        encoding="utf-8")

    literals = re.findall(r'const val (?:SCOPE|MODE)_\w+ = "([^"]+)"', run_screen)
    literals += re.findall(r'const val PROBE_MODE = "([^"]+)"', repository)
    check(len(literals) >= 5,
          "contract: the app's workflow input literals were found",
          f"got {literals}")

    for literal in literals:
        check(f'"{literal}"' in workflow or f"- {literal}" in workflow
              or literal in workflow,
              f"contract: monitor.yml offers the option {literal!r}")

    # And the input names the app sends.
    sent = set(re.findall(r'"(\w+)" to ', run_screen + repository))
    declared = set(re.findall(r"^      (\w+):$", workflow, re.M))
    unknown = sorted(sent - declared)
    check(not unknown,
          "contract: every input the app sends is declared by the workflow",
          f"undeclared: {unknown}; declared: {sorted(declared)}")


TESTS = [
    test_the_app_reads_every_field_the_report_writes,
    test_the_app_reads_a_report_from_a_run_that_found_nothing,
    test_the_report_schema_constant_matches_on_both_sides,
    test_the_app_reads_every_field_the_probe_writes,
    test_the_app_reads_a_probe_that_could_not_read_anything,
    test_the_probe_schema_constant_matches_on_both_sides,
    test_the_app_reads_the_portal_fields_the_loader_accepts,
    test_the_forms_rules_are_the_rules_the_loader_enforces,
    test_the_app_can_find_the_files_the_run_actually_produces,
    test_the_apps_workflow_inputs_match_the_workflow,
]
