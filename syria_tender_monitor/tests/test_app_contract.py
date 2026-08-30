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
