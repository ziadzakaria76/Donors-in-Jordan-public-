"""Sanctions screening.

Screening is decision support, never legal advice. The failure this module must
never have is screening everything clean because a list did not load.
"""

from __future__ import annotations

from datetime import date

import pytest

from syria_monitor.screening import (DISCLAIMER, SanctionsList, Screener, ScreeningUnavailable,
                                     normalise, parse_names)


@pytest.fixture
def screener(tmp_path):
    s = Screener(tmp_path / "cache")
    s.lists["ofac_sdn"] = SanctionsList(
        key="ofac_sdn", label="OFAC SDN", fetched=date(2026, 8, 21),
        names={normalise("Rami Makhlouf"), normalise("Al-Bara Trading Company"),
               normalise("Syrian Arab Airlines")})
    return s


def test_designated_name_matches(screener):
    hits = screener.screen(["Rami Makhlouf"])
    assert len(hits) == 1
    assert hits[0]["list"] == "OFAC SDN"
    assert hits[0]["list_fetched"] == "2026-08-21"
    assert hits[0]["note"] == DISCLAIMER


def test_designated_entity_inside_a_longer_name_matches(screener):
    assert screener.screen(["Al-Bara Trading Company LLC"])


@pytest.mark.parametrize("similar", [
    "Rani Makhlouf",          # one letter different: a different person
    "Ahmad Makhlouf",
    "Bara Trading",           # not the designated entity
    "Syrian Arab Republic",   # shares two tokens with "Syrian Arab Airlines"
])
def test_similar_but_different_names_do_not_silently_match(screener, similar):
    assert screener.screen([similar]) == []


def test_empty_list_fails_loudly_rather_than_screening_everything_clean(tmp_path):
    empty = Screener(tmp_path / "empty")
    with pytest.raises(ScreeningUnavailable):
        empty.screen(["Anyone At All"])


def test_failed_download_fails_loudly(tmp_path):
    class DeadFetcher:
        def get(self, url, **kwargs):
            class R:
                ok, status, text = False, 503, ""
            return R()

    screener = Screener(tmp_path / "cache", fetcher=DeadFetcher())
    with pytest.raises(ScreeningUnavailable):
        screener.refresh("ofac_sdn")


def test_download_that_parses_zero_names_fails_loudly(tmp_path):
    class EmptyCsvFetcher:
        def get(self, url, **kwargs):
            class R:
                ok, status = True, 200
                text = "header_only\n"
            return R()

    screener = Screener(tmp_path / "cache", fetcher=EmptyCsvFetcher())
    with pytest.raises(ScreeningUnavailable):
        screener.refresh("ofac_sdn")


def test_list_status_carries_the_fetch_date(screener):
    status = screener.list_status()
    assert status[0]["fetched"] == "2026-08-21"
    assert status[0]["names"] == 3


def test_no_output_ever_calls_a_counterparty_clear(screener):
    """The disclaimer says the word "clearance"; no hit may assert a clean result."""
    hits = screener.screen(["Rami Makhlouf"])
    blob = " ".join(str(v) for hit in hits for v in hit.values()).lower()
    for phrase in ("is clear", "no match", "cleared", "clean", "not designated"):
        assert phrase not in blob
    assert "never legal clearance" in blob


def test_screening_a_name_with_no_hit_returns_nothing_rather_than_a_verdict(screener):
    """Absence of a hit is not a finding, and is never reported as one."""
    assert screener.screen(["Wholly Unrelated Consulting GmbH"]) == []


def test_csv_parsing_picks_up_names():
    csv_text = "ent_num,SDN_Name,SDN_Type\n1,\"MAKHLOUF, Rami\",individual\n2,AL-BARA CO,entity\n"
    names = parse_names(csv_text, {"format": "csv", "name_column": 1})
    assert normalise("MAKHLOUF, Rami") in names
