"""Value parsing, including the SYP redenomination trap."""

from __future__ import annotations

from datetime import date

import pytest

from syria_monitor.money import parse_number, parse_value


@pytest.mark.parametrize("text,expected", [
    ("1.500.000", 1_500_000.0),      # European thousands
    ("1,500,000", 1_500_000.0),      # Anglo thousands
    ("1,5", 1.5),                    # European decimal
    ("1.5", 1.5),
    ("1.234.567,89", 1_234_567.89),
])
def test_number_formats(text, expected):
    assert parse_number(text) == expected


def test_a_date_is_not_a_contract_value():
    """Taking the first number in a row turns a publication date into $1."""
    assert parse_value("Published: 01 August 2026").amount is None


def test_value_requires_currency_or_magnitude():
    assert parse_value("Lot 3 of 12, package 4").amount is None
    assert parse_value("EUR 1.500.000").amount == 1_500_000.0
    assert parse_value("approximately 3.5 million EUR").amount == 3_500_000.0


def test_largest_candidate_wins():
    text = "Lot 1: EUR 250.000, Lot 2: EUR 1.750.000, reference 2026"
    assert parse_value(text).amount == 1_750_000.0


@pytest.mark.parametrize("text", ["USD 12", "USD 9,000,000,000"])
def test_implausible_values_are_missing_not_disqualifying(text):
    parsed = parse_value(text)
    assert parsed.amount is None
    assert any(f.startswith("value_implausible") for f in parsed.flags)


def test_syp_is_never_converted_and_the_two_eras_are_distinguishable(profile):
    """Same numeral, two publication dates, two different real amounts.

    Syria redenominated on 2026-01-01 (100 old = 1 new) with a 90-day
    dual-circulation window, so reading an old-SYP figure as new reports a
    contract at 100x its value -- and that error lands inside any plausibility
    band, because it produces a number that looks entirely reasonable.
    """
    before = parse_value("SYP 850,000,000", date(2025, 11, 1), profile)
    after = parse_value("SYP 850,000,000", date(2026, 6, 1), profile)

    # Neither produces a USD figure at all.
    assert before.currency == after.currency == "SYP"
    assert "currency_local:no_usd_conversion" in before.flags
    assert "currency_local:no_usd_conversion" in after.flags

    # And the two eras are not reported identically.
    assert before.flags != after.flags
    assert any(f.startswith("syp_pre_redenomination") for f in before.flags)
    assert not any(f.startswith("syp_pre_redenomination") for f in after.flags)


def test_syp_during_dual_circulation_is_flagged(profile):
    parsed = parse_value("SYP 400,000", date(2026, 2, 15), profile)
    assert any(f.startswith("syp_dual_circulation") for f in parsed.flags)


def test_syp_with_unknown_publication_date_is_flagged_ambiguous(profile):
    parsed = parse_value("SYP 400,000", None, profile)
    assert any("ambiguous" in f for f in parsed.flags)


def test_usd_value_reaches_the_tender_but_syp_does_not(profile, gate):
    """estimated_value_usd stays empty for local currency, by design."""
    from syria_monitor.fetch import Fetcher
    from syria_monitor.portals.worldbank import WorldBankPortal

    portal = WorldBankPortal({}, profile, Fetcher(), gate)
    usd = portal.to_tender({"id": "OP00460737", "title": "x", "value_text": "US$ 2,400,000"},
                           "inside_syria", "SY")
    syp = portal.to_tender({"id": "OP00460738", "title": "y", "value_text": "SYP 850,000,000",
                            "posted_date": "2025-11-01"}, "inside_syria", "SY")
    assert usd.estimated_value_usd == 2_400_000.0
    assert syp.estimated_value_usd is None
    assert syp.raw_currency == "SYP"
