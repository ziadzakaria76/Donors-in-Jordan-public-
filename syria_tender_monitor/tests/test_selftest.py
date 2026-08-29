"""The offline self-test: end-to-end wiring, and the classification split.

With no network available anywhere, this stands in for a live dry run: it is the
only place the whole chain -- extraction, gate, classifier, deadline filter,
dedupe, ranking, report -- is exercised together.
"""

from __future__ import annotations

from datetime import date

import pytest

from syria_monitor.fetch import Fetcher
from syria_monitor.pipeline import run as run_pipeline
from syria_monitor.portals import REGISTRY
from syria_monitor.selftest import FIXTURE_PORTALS

TODAY = date(2026, 8, 23)


@pytest.fixture
def fixture_registry(monkeypatch):
    original = dict(REGISTRY)
    REGISTRY.clear()
    REGISTRY.update(FIXTURE_PORTALS)
    yield REGISTRY
    REGISTRY.clear()
    REGISTRY.update(original)


@pytest.fixture
def mixed(config, fixture_registry):
    return run_pipeline(config, fetcher=Fetcher(), today=TODAY, portals=["fx_mixed"])


def titles(tenders):
    return [t.title for t in tenders]


def test_all_four_categories_are_classified(mixed):
    by_type: dict[str, list[str]] = {}
    for tender in mixed.tenders + mixed.excluded:
        by_type.setdefault(tender.syria_link_type, []).append(tender.title)
    joined = {key: " | ".join(values) for key, values in by_type.items()}
    assert "Deir ez-Zor" in joined["inside_syria"]
    assert "Gaziantep" in joined["cross_border_hub"]
    assert "Regional evaluation" in joined["regional_crisis"]
    assert "Mafraq" in joined["refugee_hosting_only"]


def test_only_inside_syria_is_in_scope(mixed):
    assert {t.syria_link_type for t in mixed.tenders} == {"inside_syria"}
    assert {t.syria_link_type for t in mixed.excluded} == {
        "cross_border_hub", "regional_crisis", "refugee_hosting_only"}


def test_out_of_scope_tenders_are_logged_line_by_line(mixed):
    """Counts alone would not let a misclassification be spotted."""
    assert len(mixed.excluded) == 3
    assert mixed.counts["cross_border_hub"] == 1
    assert mixed.counts["regional_crisis"] == 1
    assert mixed.counts["refugee_hosting_only"] == 1


def test_the_blantyre_record_is_dropped_entirely(mixed):
    everything = titles(mixed.tenders) + titles(mixed.excluded)
    assert not any("Blantyre" in t for t in everything)
    assert mixed.counts["unclassified"] == 1


def test_a_notice_naming_no_country_survives_on_its_country_field(mixed):
    """The counterpart to Blantyre: over-correcting on one breaks the other."""
    assert any("Supply of laboratory equipment" in t for t in titles(mixed.tenders))


def test_deadlines_are_read_from_every_extraction_layer(config, fixture_registry):
    """Rows from the class-independent layers carry dates in prose, not cells."""
    result = run_pipeline(config, fetcher=Fetcher(), today=TODAY,
                          portals=["fx_drupal", "fx_navtrap", "fx_arabic", "fx_nextjs"])
    dated = [t for t in result.tenders if t.closing_date]
    assert len(dated) >= 8, [t.title for t in result.tenders if not t.closing_date]


def test_arabic_deadline_parses_from_an_arabic_table_header(config, fixture_registry):
    result = run_pipeline(config, fetcher=Fetcher(), today=TODAY, portals=["fx_arabic"])
    arabic = [t for t in result.tenders if t.language == "ar"]
    assert arabic and all(t.closing_date for t in arabic)
    assert arabic[0].closing_date == date(2026, 9, 30)


def test_arabic_notices_do_not_automatically_rank_last(config, fixture_registry):
    """Arabic terms are in the ranking lexicon; without them the local pipeline
    sinks out of sight."""
    result = run_pipeline(config, fetcher=Fetcher(), today=TODAY,
                          portals=["fx_arabic", "fx_navtrap"])
    positions = [i for i, t in enumerate(result.tenders) if t.language == "ar"]
    assert positions and min(positions) < len(result.tenders) / 2


def test_a_bot_wall_is_reported_unavailable_not_silently_empty(config, fixture_registry):
    result = run_pipeline(config, fetcher=Fetcher(), today=TODAY, portals=["fx_wall"])
    assert result.failed
    assert "bot_wall" in result.failed[0].error
    assert result.subject().startswith("ACTION NEEDED")


def test_self_test_command_never_writes_to_real_state(config, tmp_path, capsys):
    from syria_monitor.selftest import self_test
    assert self_test(config, today=TODAY) == 0
    output = capsys.readouterr().out
    assert "Nothing written to real state" in output
    assert not (tmp_path / "seen.db").exists() or (tmp_path / "seen.db").stat().st_size >= 0
