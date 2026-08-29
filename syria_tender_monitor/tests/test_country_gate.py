"""The universal country check.

These are the regressions that put phantom tenders into a live report, plus the
counterpart that over-correcting on them breaks. A build that passes only one of
the pair is not finished.
"""

from __future__ import annotations

import pytest

from syria_monitor.fetch import Fetcher
from syria_monitor.gate import GateStats
from syria_monitor.matching import ACCEPT, REJECT, UNKNOWN
from syria_monitor.portals import REGISTRY
from syria_monitor.portals.base import BasePortal
from syria_monitor.portals.worldbank import WorldBankPortal


# ------------------------------------------------------------------ tri-state
def test_field_naming_our_country_accepts(matcher):
    assert matcher.country_verdict({"project_ctry_name": "Syrian Arab Republic"}) is ACCEPT


def test_field_naming_another_country_rejects(matcher):
    assert matcher.country_verdict({"countryshortname": "Malawi"}) is REJECT


def test_no_country_field_is_unknown(matcher):
    assert matcher.country_verdict({"title": "Supply of laboratory equipment"}) is UNKNOWN


def test_countryshortname_is_read_as_a_response_field(matcher):
    """The same name is ignored as a request parameter and meaningful as a
    response field. Read it, do not send it."""
    assert matcher.country_verdict({"countryshortname": "Syrian Arab Republic"}) is ACCEPT
    assert "countryshortname" not in WorldBankPortal({}, {}, None, None)._params()


# --------------------------------------------------------- the Blantyre regression
def test_full_text_match_cannot_rescue_a_foreign_country_field(gate):
    """A World-Bank-shaped record whose country field says Malawi and whose
    indexed description contains "Syria" must be rejected.

    qterm is a full-text search: every record it returns contains the search
    word somewhere in its indexed text. If that body is then used as the
    client-side check, the second layer re-reads the exact field the first one
    matched and can never reject anything -- 500 of 500 kept, and water-supply
    consultancies in Blantyre, Malawi in the report.
    """
    record = {
        "id": "OP00460999",
        "title": "Water supply and sanitation consultancy services",
        "countryshortname": "Malawi",
        "project_ctry_name": "Malawi",
        "description": "Consultants with experience in Syria an advantage. Syria, Syria.",
        "_safe_text_fields": ["title"],
    }
    keep, link_type, _ = gate.check(record, GateStats())
    assert keep is False
    assert link_type != "inside_syria"


def test_refugee_wording_is_classified_not_dropped_invisibly(gate):
    """A host-country tender that merely mentions Syrians is labelled, kept for
    audit, and left out of scope by the scope filter -- not silently discarded,
    which would make a misclassification impossible to spot."""
    record = {"title": "Education programme for Syrian refugee children",
              "country": "Türkiye", "_safe_text_fields": ["title"]}
    keep, link_type, delivery = gate.check(record, GateStats())
    assert keep is True
    assert link_type == "refugee_hosting_only"
    assert delivery == "TR"


def test_a_cross_border_hub_tender_is_kept_for_audit(gate):
    record = {"title": "Whole of Syria WASH coordination, duty station Gaziantep",
              "place_of_performance_country": "TR", "_safe_text_fields": ["title"]}
    keep, link_type, _ = gate.check(record, GateStats())
    assert keep is True
    assert link_type == "cross_border_hub"


# --------------------------------------------------------- the counterpart test
def test_country_field_wins_over_a_title_that_names_no_country(gate):
    """Over-correcting on Blantyre breaks this one.

    "Supply of laboratory equipment, Package 3" names no country at all. The
    country field says ours, so it is kept -- a text check must not be allowed
    to second-guess an explicit field.
    """
    record = {"id": "OP00460737", "title": "Supply of laboratory equipment, Package 3",
              "project_ctry_name": "Syrian Arab Republic", "_safe_text_fields": ["title"]}
    keep, link_type, delivery = gate.check(record, GateStats())
    assert keep is True
    assert link_type == "inside_syria"
    assert delivery == "SY"


def test_no_country_field_falls_back_to_text(gate):
    keep, _, _ = gate.check({"title": "Rehabilitation of the Aleppo water network"}, GateStats())
    assert keep is True
    keep, _, _ = gate.check({"title": "Rehabilitation of the Blantyre water network"}, GateStats())
    assert keep is False


# ------------------------------------------------- a portal cannot skip the check
class RoguePortal(BasePortal):
    """A newly added portal whose author forgot about country filtering."""

    name = "rogue"
    label = "Rogue"
    url = "https://example.invalid/notices"

    def fetch_tenders(self):
        return [
            {"title": "Water supply consultancy", "country": "Malawi",
             "_safe_text_fields": ["title"]},
            {"title": "Education project", "country": "Barbados", "_safe_text_fields": ["title"]},
            {"title": "Rehabilitation works", "project_ctry_name": "Syrian Arab Republic",
             "_safe_text_fields": ["title"]},
        ]


def test_a_portal_that_does_no_filtering_still_cannot_ship_worldwide_notices(profile, gate):
    outcome = RoguePortal({}, profile, Fetcher(), gate).collect()
    assert [t.title for t in outcome.tenders] == ["Rehabilitation works"]
    assert outcome.stats.seen == 3
    assert outcome.stats.rejected_by_field == 2


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_no_portal_overrides_the_gated_collect(name):
    """collect() is where the shared check runs. A portal that overrode it could
    opt out by omission, so overriding it fails here rather than in production."""
    assert "collect" not in REGISTRY[name].__dict__, f"{name} overrides collect()"


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_every_portal_declares_its_own_fetch(name):
    cls = REGISTRY[name]
    assert any("fetch_tenders" in klass.__dict__ for klass in cls.__mro__), name


# ------------------------------------------------------------ link construction
@pytest.mark.parametrize("notice_id,expected", [
    ("OP00460737", "https://projects.worldbank.org/en/projects-operations/"
                   "procurement-detail/OP00460737"),
    ("OP1234567", "https://projects.worldbank.org/en/projects-operations/"
                  "procurement-detail/OP1234567"),
])
def test_notice_id_builds_a_link(notice_id, expected):
    assert WorldBankPortal.build_link(notice_id) == expected


@pytest.mark.parametrize("bad_id", ["P175447", "1234567", "", "OP123", "op00460737x", None])
def test_project_ids_produce_no_link_rather_than_a_404(bad_id):
    """A dead link is worse than no link, because a dead link looks checked."""
    assert WorldBankPortal.build_link(bad_id) is None
