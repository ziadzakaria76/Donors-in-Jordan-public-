"""Scoring engine behaviour.

The postings below are test fixtures, written by hand to exercise specific
rules. They live here and only here — nothing in this file is ever loaded into
the application database or shown in the feed.
"""

from __future__ import annotations

import pytest

from app.adapters.base import JobPosting
from app.scoring.engine import ScoringEngine, normalize, score_all
from app.scoring.profile import ProfileError, load_profile, validate_profile


@pytest.fixture(scope="module")
def profile():
    return load_profile()


@pytest.fixture(scope="module")
def engine(profile):
    return ScoringEngine(profile)


def posting(**kw) -> JobPosting:
    base = dict(
        source_id="test",
        source_job_id=kw.get("title", "x"),
        title="Project Director",
        employer="Some Contractor",
        url="https://example.com/job/1",
    )
    base.update(kw)
    return JobPosting(**base)


# -- the profile itself ------------------------------------------------------

def test_shipped_profile_is_valid(profile):
    validate_profile(profile)


def test_validator_rejects_a_signal_that_can_never_fire():
    with pytest.raises(ProfileError, match="no keywords"):
        validate_profile({
            "signals": [{"id": "dud", "weight": 10}],
            "thresholds": {"moderate": 60, "strong": 80},
        })


def test_validator_rejects_duplicate_rule_ids():
    rule = {"id": "same", "weight": 5, "keywords": ["a"]}
    with pytest.raises(ProfileError, match="Duplicate"):
        validate_profile({
            "signals": [rule, dict(rule)],
            "thresholds": {"moderate": 60, "strong": 80},
        })


# -- normalization -----------------------------------------------------------

@pytest.mark.parametrize("raw, needle", [
    ("Design-Build", "design build"),
    ("design & build", "design & build"),
    ("MEP/HVAC", "mep hvac"),
    ("إدارة المشاريع", "اداره المشاريع"),
])
def test_normalize_folds_separators_and_arabic_orthography(raw, needle):
    assert needle in normalize(raw)


# -- determinism -------------------------------------------------------------

def test_same_posting_scores_identically_every_time(engine):
    job = posting(
        title="Stadium Delivery Director",
        employer="Qiddiya Investment Company",
        location="Riyadh, Saudi Arabia",
        description="District cooling and MEP delivery for a new sports venue.",
    )
    first = engine.score(job)
    runs = [engine.score(job) for _ in range(25)]
    assert all(r.score == first.score for r in runs)
    assert all(r.explain() == first.explain() for r in runs)


def test_breakdown_always_reconciles_to_the_raw_score(engine):
    job = posting(
        title="MEP Operations Director",
        employer="Nesma & Partners",
        location="Jeddah",
        description="FIDIC claims, EOT, commissioning of chilled water plant.",
    )
    result = engine.score(job)
    assert sum(c.contribution for c in result.components) == result.raw_score


# -- the core match ----------------------------------------------------------

def test_signature_job_scores_strongly_and_lands_in_lane_b(engine):
    job = posting(
        title="Stadium Delivery Director",
        employer="Qiddiya Investment Company",
        location="Riyadh",
        description=(
            "Lead delivery of a 45,000-seat stadium including outdoor cooling, "
            "the district cooling energy centre and all MEP packages. FIDIC "
            "contract administration, EOT and claims. Design and build."
        ),
    )
    result = engine.score(job)
    assert result.lane == "B"
    assert result.employer_tier == 1
    assert result.score >= 80 and result.band == "strong"
    assert result.visible
    fired = {c.signal_id for c in result.components}
    assert {"stadium_venue", "district_cooling", "outdoor_cooling", "mep",
            "fidic_claims", "loc_riyadh", "employer_tier"} <= fired


def test_contractor_operations_role_lands_in_lane_a(engine):
    result = engine.score(posting(
        title="Operations Director",
        employer="El Seif Engineering",
        location="Riyadh",
        description="P&L ownership across a portfolio of design and build projects.",
    ))
    assert result.lane == "A"
    assert result.employer_tier == 1


def test_target_employer_disambiguates_a_lane_neutral_title(engine):
    """A senior title that matches no lane list still lands via the employer."""
    result = engine.score(posting(
        title="Executive Director, Delivery Assurance",
        employer="Almabani General Contractors",
        location="Riyadh",
    ))
    assert result.lane == "A"
    assert any(c.signal_id == "seniority_generic" for c in result.components)


# -- rejection ---------------------------------------------------------------

def test_junior_role_is_pushed_far_down(engine):
    result = engine.score(posting(
        title="Site Engineer",
        employer="Al Bawani",
        location="Riyadh",
        description="Supervise MEP installation works on site.",
    ))
    assert result.score < 60
    assert any(c.signal_id == "below_director" for c in result.components)


def test_out_of_sector_role_is_downranked(engine):
    result = engine.score(posting(
        title="Projects Director",
        employer="Some Contractor",
        location="Jubail",
        description="Delivery of a refinery expansion and offshore pipeline scope.",
    ))
    assert any(c.signal_id == "out_of_sector" for c in result.components)
    assert result.score < 60


def test_neom_is_flagged_and_downranked_but_not_hidden(engine):
    result = engine.score(posting(
        title="Delivery Director",
        employer="NEOM",
        location="Tabuk",
        description="Stadium and district cooling delivery for THE LINE.",
    ))
    assert "high_risk_employer" in result.flags
    assert result.visible, "NEOM roles are shown, marked, near the bottom"
    assert any(c.signal_id == "neom_risk" and c.contribution < 0
               for c in result.components)


def test_saudi_nationals_only_posting_is_excluded_with_a_reason(engine):
    result = engine.score(posting(
        title="Operations Director",
        employer="Al Bawani",
        location="Riyadh",
        description="Saudi nationals only. Nitaqat requirement applies.",
    ))
    assert result.excluded
    assert not result.visible
    assert result.exclusions[0].rule_id == "saudi_nationals_only"
    assert result.exclusions[0].matched  # the reason is never empty


def test_arabic_nationality_restriction_is_caught(engine):
    result = engine.score(posting(
        title="مدير العمليات",
        employer="شركة البواني",
        location="الرياض",
        description="مطلوب مدير عمليات، سعودي الجنسية فقط.",
    ))
    assert result.excluded


# -- Arabic postings ---------------------------------------------------------

def test_arabic_posting_scores_on_arabic_keywords(engine):
    result = engine.score(posting(
        title="مدير المشاريع",
        employer="نسما وشركاه",
        location="الرياض",
        description="تنفيذ ملعب رياضي مع أعمال تبريد المناطق والأعمال الكهروميكانيكية.",
        language="ar",
    ))
    fired = {c.signal_id for c in result.components}
    assert "stadium_venue" in fired
    assert "district_cooling" in fired
    assert "loc_riyadh" in fired
    assert result.lane == "A"


# -- facilities management ---------------------------------------------------

def test_weak_fm_role_is_suppressed_with_a_stated_reason(engine):
    result = engine.score(posting(
        title="Facilities Management Director",
        employer="Some Operator",
        location="Riyadh",
        description="Soft services and hard services across a retail portfolio.",
    ))
    assert result.suppressed
    assert not result.visible
    assert "below the FM bar" in result.suppression_reason


def test_strong_fm_role_with_delivery_scope_survives(engine):
    result = engine.score(posting(
        title="Facilities Management Director",
        employer="Qiddiya Investment Company",
        location="Riyadh",
        description=(
            "Asset lifecycle and delivery of the district cooling energy centre, "
            "MEP systems and stadium commissioning. FIDIC claims and EOT."
        ),
    ))
    assert result.score >= 75
    assert not result.suppressed, "an FM role clearing the bar must still be seen"


# -- consultancy exception ---------------------------------------------------

def test_hill_international_escapes_the_consultancy_penalty(engine):
    kw = dict(
        title="Programme Director",
        location="Riyadh",
        description="Project management consultancy services, claims and entitlement.",
    )
    hill = engine.score(posting(employer="Hill International", **kw))
    other = engine.score(posting(employer="Generic PMC Consultants", **kw))
    assert not any(c.signal_id == "pmc_consultancy" for c in hill.components)
    assert any(c.signal_id == "pmc_consultancy" for c in other.components)
    assert hill.score > other.score


# -- location group ----------------------------------------------------------

def test_only_the_strongest_location_signal_fires(engine):
    result = engine.score(posting(
        title="Project Director",
        employer="Some Contractor",
        location="Riyadh",
        description="Projects across Riyadh, Jeddah, Dammam and Abha.",
    ))
    locations = [c for c in result.components if c.signal_id.startswith("loc_")]
    assert len(locations) == 1
    assert locations[0].signal_id == "loc_riyadh"


# -- salary ------------------------------------------------------------------

def test_stated_salary_below_target_is_flagged_not_hidden(engine):
    result = engine.score(posting(
        title="Operations Director",
        employer="Al Bawani",
        location="Riyadh",
        salary_max=40000,
        salary_currency="SAR",
    ))
    assert "below_target_salary" in result.flags
    assert result.visible, "below-target roles are flagged, never hidden"


def test_unstated_salary_is_not_penalised(engine):
    result = engine.score(posting(
        title="Operations Director", employer="Al Bawani", location="Riyadh",
    ))
    assert "below_target_salary" not in result.flags


# -- warm routes -------------------------------------------------------------

def test_warm_route_lifts_the_score_and_names_the_count(engine):
    job = posting(
        title="Delivery Director", employer="Diriyah Company", location="Riyadh",
    )
    cold = engine.score(job, warm_contact_count=0)
    warm = engine.score(job, warm_contact_count=2)
    assert warm.score > cold.score
    assert warm.warm_route and warm.warm_contact_count == 2
    assert "2 contacts" in warm.explain()


def test_warm_job_outranks_an_equivalent_cold_job(engine):
    warm_job = posting(
        source_job_id="warm", title="Delivery Director",
        employer="Diriyah Company", location="Riyadh",
    )
    cold_job = posting(
        source_job_id="cold", title="Delivery Director",
        employer="Diriyah Company", location="Riyadh",
        url="https://example.com/job/2",
    )
    ordered = score_all(
        engine, [cold_job, warm_job], {warm_job.fingerprint: 1},
    )
    assert ordered[0][0].source_job_id == "warm"


# -- posting integrity -------------------------------------------------------

def test_a_posting_without_a_source_url_cannot_exist():
    with pytest.raises(ValueError, match="url"):
        JobPosting(
            source_id="s", source_job_id="1", title="t", employer="e", url="",
        )


def test_a_posting_url_must_be_absolute():
    with pytest.raises(ValueError, match="absolute"):
        JobPosting(
            source_id="s", source_job_id="1", title="t", employer="e",
            url="/jobs/1",
        )


def test_fingerprint_is_stable_across_title_rewording():
    a = posting(title="Project Director", source_job_id="REQ-1")
    b = posting(title="Project Director (Riyadh)", source_job_id="REQ-1")
    assert a.fingerprint == b.fingerprint


def test_ranking_discriminates_between_jobs_that_both_display_as_100(engine):
    """Two capped jobs must still order by their real strength."""
    stronger = posting(
        source_job_id="stronger", title="Stadium Delivery Director",
        employer="Qiddiya Investment Company", location="Riyadh",
        description=(
            "Stadium, outdoor cooling, district cooling energy centre, MEP, "
            "FIDIC, EOT, claims, design and build, commissioning, P&L, FIFA "
            "World Cup venue experience essential."
        ),
    )
    weaker = posting(
        source_job_id="weaker", title="Project Director",
        employer="Diriyah Company", location="Riyadh",
        url="https://example.com/job/2",
        description=(
            "Stadium delivery with district cooling scope, MEP packages, "
            "FIDIC administration and design and build procurement."
        ),
    )
    assert engine.score(stronger).score == engine.score(weaker).score == 100
    ordered = score_all(engine, [weaker, stronger])
    assert ordered[0][0].source_job_id == "stronger"


def test_a_weak_warm_job_does_not_leapfrog_a_strong_cold_one(engine):
    weak_warm = posting(
        source_job_id="weak-warm", title="Operations Manager",
        employer="Diriyah Company", location="Abha",
    )
    strong_cold = posting(
        source_job_id="strong-cold", title="Stadium Delivery Director",
        employer="Qiddiya Investment Company", location="Riyadh",
        url="https://example.com/job/2",
        description="District cooling, MEP, FIDIC claims, outdoor cooling.",
    )
    ordered = score_all(
        engine, [weak_warm, strong_cold], {weak_warm.fingerprint: 3},
    )
    assert ordered[0][0].source_job_id == "strong-cold"


def test_arabic_employer_name_resolves_to_the_tier_1_target(engine):
    result = engine.score(posting(
        title="مدير المشاريع", employer="نسما وشركاه", location="الرياض",
        description="تنفيذ ملعب رياضي مع أعمال تبريد المناطق.",
    ))
    assert result.employer_tier == 1, "Arabic employer names must match the target list"
    assert any(c.signal_id == "employer_tier" for c in result.components)
