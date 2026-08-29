"""Test wiring.

The database and output directory are redirected to a temp folder for every
test, so the suite can never touch real state. Nothing here needs network or
credentials: the whole suite runs offline, in CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("MONITOR_DB_PATH", str(tmp_path / "seen.db"))
    monkeypatch.setenv("MONITOR_OUTPUT_DIR", str(tmp_path / "output"))
    for name in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET",
                 "GRAPH_SENDER", "REPORT_TO", "REPORT_CC", "SAM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


@pytest.fixture(scope="session")
def profile() -> dict:
    return yaml.safe_load((ROOT / "profiles" / "syria.yml").read_text(encoding="utf-8"))


@pytest.fixture
def matcher(profile):
    from syria_monitor.matching import CountryMatcher
    return CountryMatcher(profile)


@pytest.fixture
def classifier(profile, matcher):
    from syria_monitor.classify import Classifier
    return Classifier(profile, matcher)


@pytest.fixture
def gate(profile, matcher, classifier):
    from syria_monitor.gate import CountryGate
    return CountryGate(profile, matcher, classifier)


@pytest.fixture
def config(profile, tmp_path):
    from syria_monitor.config import Config
    data = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    data["state"]["db_path"] = str(tmp_path / "seen.db")
    data["output"]["dir"] = str(tmp_path / "output")
    return Config(data, profile)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
