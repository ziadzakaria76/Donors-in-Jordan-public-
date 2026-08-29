"""Country matching -- the module where a Syria build differs most sharply.

Every case here was a real defect or a documented trap. The four-row pattern
table is a regression guard: a future "simplification" back to \\bsyria\\b or
\\bsyria\\w*\\b breaks one end or the other, and both are caught here.
"""

from __future__ import annotations

import re

import pytest

from syria_monitor.models import INSIDE, REFUGEE_HOSTING


# --------------------------------------------------------------- the pattern table
@pytest.mark.parametrize("pattern,text,expected", [
    # \bsyria\b: rejects the negatives, and silently MISSES the formal UN name
    (r"\bsyria\b", "Syria", True),
    (r"\bsyria\b", "Syrian Arab Republic", False),          # the silent miss
    (r"\bsyria\b", "Assyrian", False),
    (r"\bsyria\b", "Syriac", False),
    # \bsyria\w*\b: fixes the miss, and re-admits Syriac
    (r"\bsyria\w*\b", "Syria", True),
    (r"\bsyria\w*\b", "Syrian Arab Republic", True),
    (r"\bsyria\w*\b", "Assyrian", False),
    (r"\bsyria\w*\b", "Syriac", True),                      # the false match
    # \bsyrian?\b: correct at both ends
    (r"\bsyrian?\b", "Syria", True),
    (r"\bsyrian?\b", "Syrian Arab Republic", True),
    (r"\bsyrian?\b", "Assyrian", False),
    (r"\bsyrian?\b", "Syriac", False),
])
def test_documented_pattern_behaviour(pattern, text, expected):
    assert bool(re.search(pattern, text, re.IGNORECASE)) is expected


# ------------------------------------------------------------------- the matcher
@pytest.mark.parametrize("text", [
    "Syria",
    "Syrian Arab Republic",                 # the World Bank's own spelling
    "Rehabilitation works, Syrian Arab Republic",
    "Deir Ezzor water supply",
    "Dayr az Zawr rehabilitation",
    "Deir al-Zour health facilities",
    "Al-Hasakah sanitation",
    "As-Suwayda road works",
    "Idleb shelter programme",
    "Wiederaufbau in Syrien",               # German
    "Reconstruction en Syrie",              # French
    "سورية",
    "السورية",
    "الجمهورية العربية السورية",            # formal Arabic name
    "دمشق",
    "contact@mopic.gov.sy",
    "see mopic.gov.sy for details",
])
def test_matches(matcher, text):
    assert matcher.matches_text(text), text


@pytest.mark.parametrize("text", [
    "Assyrian community centre, Iraq",
    "Assyrian cultural heritage project, Nineveh",
    "Syriac Orthodox school, Lebanon",
    "Syriac language teaching materials, Sweden",
    "Assyrien Kulturzentrum Berlin",        # German negative
    "Damascus, MD water main replacement",  # US municipal contract
    "Damascus, Oregon road resurfacing",
    "Damascus Township drainage study",
    "ministry.system upgrade",              # .sy must not match inside a word
    "syria.desk@ngo.example.com",           # address stripped before matching
    "آشوري",
    "سرياني",
])
def test_does_not_match(matcher, text):
    assert not matcher.matches_text(text), text


def test_bare_ambiguous_place_needs_corroboration(matcher):
    """A single ambiguous place name is not enough on its own."""
    assert not matcher.matches_text("Damascus community centre refurbishment")
    assert matcher.matches_text("Damascus and Aleppo community centres")


def test_sy_tld_is_positive_evidence_but_a_foreign_address_is_not(matcher):
    assert matcher.matches_text("Enquiries: procurement@mopic.gov.sy")
    assert not matcher.matches_text("Enquiries: syria.desk@ngo.example.com")


def test_arabic_stem_beats_the_full_word(profile):
    """سوري matches five forms; سوريا matches only itself."""
    from syria_monitor.matching import CountryMatcher
    stem_profile = dict(profile)
    assert profile["arabic_stems"] == ["سوري"], "the stem must stay سوري, not سوريا"

    naive = dict(stem_profile, arabic_stems=["سوريا"], strong_terms=[], places=[], tld=None)
    naive_matcher = CountryMatcher(naive)
    for form in ("سورية", "السورية", "السوري", "الجمهورية العربية السورية"):
        assert not naive_matcher.matches_text(form), f"سوريا should miss {form}"

    good = dict(stem_profile, strong_terms=[], places=[], tld=None)
    good_matcher = CountryMatcher(good)
    for form in ("سوريا", "سورية", "السورية", "السوري", "الجمهورية العربية السورية"):
        assert good_matcher.matches_text(form), form
    for negative in ("آشوري", "سرياني"):
        assert not good_matcher.matches_text(negative), negative


# ---------------------------------------------------------------- classification
def test_refugee_tender_is_classified_not_dropped(classifier):
    """The biggest false-positive class must be labelled, not silently dropped."""
    link_type, delivery = classifier.classify(
        {"country": "Jordan"}, "Education support for Syrian refugee children, Mafraq")
    assert link_type == REFUGEE_HOSTING
    assert delivery == "JO"


def test_delivery_location_beats_beneficiary_nationality(classifier):
    link_type, _ = classifier.classify(
        {"delivery_country": "SY"}, "Support to Syrian refugees returning to Aleppo")
    assert link_type == INSIDE


def test_a_lone_ambiguous_place_name_is_a_known_limitation(matcher):
    """"Damascus" on its own is not enough, by design -- and that has a cost.

    A notice reading only "Consulting services for water supply rehabilitation,
    Damascus" is NOT matched, because Damascus is also a town in Maryland,
    Oregon, Virginia and Georgia, and SAM.gov and UK Find a Tender scan whole
    national corpora. Any corroboration rescues it: a second place, the country
    name, a .sy address, or a country field on the record.

    This test exists so the limitation is visible rather than discovered. If
    real captures show a portal routinely naming the city alone, the fix is a
    per-portal corroboration default for that source -- not loosening the
    matcher globally, which would re-admit US municipal contracts.
    """
    bare = "Consulting services for water supply rehabilitation, Damascus"
    assert not matcher.matches_text(bare)

    assert matcher.matches_text(bare + ", Syria")
    assert matcher.matches_text(bare + " and Aleppo")
    assert matcher.matches_text(bare + " - contact procurement@mopic.gov.sy")
