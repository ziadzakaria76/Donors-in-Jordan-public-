"""Scoring a posting against the frozen profile.

ranking_mode is role_fit_only, so grade is recorded and never weighted: a
"Specialist, Hepatology" competes with a "Consultant Gastroenterologist" on
discipline fit alone. That is a deliberate consequence of the profile, not an
oversight -- Gulf employers use the two titles for overlapping seniority and
filtering on the word would drop real matches.

Two matching rules earn their complexity:

  Abbreviations match whole-word only. "GI" as a substring appears inside
  "surgical", "region" and "logistics"; as a token it means the specialty.
  The same guard applies to IBD, EUS and MASLD.

  Exclusions apply to the title only. A posting whose *department* is
  "Nursing Services" may still be the consultant post that department is
  recruiting; a posting whose *title* is "Staff Nurse" never is.
"""

from __future__ import annotations

import re
from typing import Any

from .model import Posting

# Where a term matched matters more than how many times it did. Each category
# contributes its best match once, and the categories sum.
TITLE_WEIGHTS = {"core": 55, "subspecialties": 50, "procedures": 50, "abbreviations": 35, "adjacent": 12}
OTHER_WEIGHTS = {"core": 25, "subspecialties": 22, "procedures": 20, "abbreviations": 15, "adjacent": 5}
LOCATION_BONUS = 5
MAX_SCORE = 100

# Postings name a city or an initialism far more often than the country the
# frozen profile lists, so "Dubai" and "UAE" have to resolve to "united arab
# emirates" for the location bonus to mean anything. This lives here rather
# than in sources.yaml because the profile block is frozen -- and because
# these are facts about geography, not preferences about the search.
LOCATION_ALIASES = {
    "saudi arabia": ["ksa", "saudi", "riyadh", "jeddah", "dammam", "khobar", "al khobar",
                     "makkah", "mecca", "madinah", "medina", "taif", "abha", "buraidah",
                     "hofuf", "al ahsa", "qassim", "dhahran", "jubail", "yanbu", "najran"],
    "united arab emirates": ["uae", "u.a.e", "emirates", "abu dhabi", "dubai", "sharjah",
                             "al ain", "ajman", "fujairah", "ras al khaimah", "umm al quwain"],
    "qatar": ["doha", "al wakrah", "al rayyan"],
    "oman": ["muscat", "salalah", "sohar", "nizwa", "seeb"],
    "bahrain": ["manama", "muharraq", "riffa", "busaiteen"],
    "kuwait": ["kuwait city", "hawalli", "salmiya", "jahra"],
    "jordan": ["amman", "irbid", "zarqa", "aqaba", "madaba"],
}


def _contains(haystack: str, term: str, whole_word: bool) -> bool:
    if not haystack or not term:
        return False
    if whole_word:
        return re.search(rf"\b{re.escape(term)}\b", haystack) is not None
    return term in haystack


class Scorer:
    def __init__(self, profile: dict[str, Any]):
        self.profile = profile
        specialty = profile.get("specialty") or {}
        self.terms: dict[str, list[str]] = {
            "core": [t.lower() for t in specialty.get("core") or []],
            "procedures": [t.lower() for t in specialty.get("procedures") or []],
            "subspecialties": [t.lower() for t in specialty.get("subspecialties") or []],
            "abbreviations": [t.lower() for t in specialty.get("abbreviations") or []],
            "adjacent": [t.lower() for t in profile.get("adjacent") or []],
        }
        self.exclude = [t.lower() for t in profile.get("exclude") or []]
        self.grades = [t.lower() for t in profile.get("grades") or []]
        self.locations = [t.lower() for t in profile.get("locations") or []]
        # Expand each target country into the strings a posting might actually
        # carry. Unknown countries simply contribute no aliases.
        self.location_terms: list[str] = []
        for country in self.locations:
            self.location_terms.append(country)
            self.location_terms.extend(LOCATION_ALIASES.get(country, []))
        self.threshold = int(profile.get("shortlist_min_score", 55))

    def excluded_by(self, title: str) -> str | None:
        low = (title or "").lower()
        for term in self.exclude:
            if _contains(low, term, whole_word=True):
                return term
        return None

    def detect_grade(self, posting: Posting) -> str:
        """Report the grade the title implies. Recorded, never scored."""
        low = f"{posting.title} {posting.grade}".lower()
        for grade in sorted(self.grades, key=len, reverse=True):
            if _contains(low, grade, whole_word=True):
                return grade
        return ""

    def score(self, posting: Posting) -> Posting:
        reasons: list[str] = []
        matched: list[str] = []

        blocker = self.excluded_by(posting.title)
        if blocker:
            posting.score = 0
            posting.shortlisted = False
            posting.score_reasons = [f"excluded: title contains '{blocker}'"]
            posting.matched_terms = []
            return posting

        title = posting.title.lower()
        other = f"{posting.department} {posting.employment_type}".lower()

        total = 0
        for category, terms in self.terms.items():
            whole_word = category == "abbreviations"
            hit_title = next((t for t in terms if _contains(title, t, whole_word)), None)
            hit_other = next((t for t in terms if _contains(other, t, whole_word)), None)

            if hit_title:
                points = TITLE_WEIGHTS[category]
                total += points
                matched.append(hit_title)
                reasons.append(f"title matches {category} '{hit_title}' (+{points})")
            elif hit_other:
                points = OTHER_WEIGHTS[category]
                total += points
                matched.append(hit_other)
                reasons.append(f"department matches {category} '{hit_other}' (+{points})")

        location = f"{posting.location} {posting.country}".lower()
        # Whole-word, so "uae" does not fire on "nuance" and "oman" does not
        # fire on "Romania".
        hit_location = next(
            (loc for loc in self.location_terms if _contains(location, loc, whole_word=True)),
            None,
        )
        if hit_location:
            total += LOCATION_BONUS
            reasons.append(f"target location '{hit_location}' (+{LOCATION_BONUS})")

        grade = self.detect_grade(posting)
        if grade:
            posting.grade = grade
            reasons.append(f"grade '{grade}' (not scored; ranking_mode is role_fit_only)")

        if not matched:
            reasons.append("no specialty term matched")

        posting.score = min(total, MAX_SCORE)
        posting.matched_terms = sorted(set(matched))
        posting.score_reasons = reasons
        posting.shortlisted = posting.score >= self.threshold
        return posting

    def score_all(self, postings: list[Posting]) -> list[Posting]:
        return [self.score(p) for p in postings]
