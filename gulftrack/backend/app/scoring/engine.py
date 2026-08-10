"""Deterministic scoring.

Three properties this module must never lose:

1. The same posting scored twice produces the same number. No clocks, no
   randomness, no language model, no network.
2. Every score decomposes into named signals with their contributions, so the
   number can be argued with and the weight behind it changed in Settings.
3. Nothing is silently discarded. A job removed from the feed carries the
   reason that removed it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from app.adapters.base import JobPosting

# Arabic orthography varies between postings for the same word: alef carries
# optional hamza, yaa and alef maqsura are used interchangeably, and diacritics
# and tatweel are decorative. Fold all of it before matching or half the Arabic
# listings miss keywords that are plainly present to a reader.
_AR_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_AR_FOLD = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي",
    "ؤ": "و",
    "ة": "ه",
})


def normalize(text: str | None) -> str:
    """Fold text to a stable comparison form. Pure function, no side effects."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _AR_DIACRITICS.sub("", text)
    text = text.translate(_AR_FOLD)
    text = text.lower()
    # Collapse whitespace and the punctuation that separates words, so
    # "design-build" and "design build" are the same phrase.
    text = re.sub(r"[‏‎]", "", text)
    text = re.sub(r"[\s\-_/\\|·•,;:()\[\]{}\"'’]+", " ", text)
    return f" {text.strip()} "


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Word-boundary matcher for a keyword, tolerant of internal punctuation.

    Built from the normalized keyword so it agrees with normalize() about what
    a word separator is. \\b works for Arabic here because Arabic letters are
    word characters under Python's Unicode-aware \\w.
    """
    folded = normalize(keyword).strip()
    escaped = r"\s+".join(re.escape(part) for part in folded.split(" ") if part)
    return re.compile(rf"(?<!\w){escaped}(?!\w)")


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    """One signal that fired, and what it contributed."""

    signal_id: str
    label: str
    contribution: int
    matched: tuple[str, ...] = ()

    def __str__(self) -> str:
        sign = "+" if self.contribution >= 0 else "−"
        return f"{self.label} {sign}{abs(self.contribution)}"


@dataclass(frozen=True, slots=True)
class Exclusion:
    """A reason this posting was removed from the feed."""

    rule_id: str
    label: str
    matched: tuple[str, ...] = ()


@dataclass(slots=True)
class ScoreResult:
    raw_score: int
    score: int
    lane: str | None
    lane_label: str | None
    employer_tier: int | None
    components: list[ScoreComponent] = field(default_factory=list)
    exclusions: list[Exclusion] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    warm_route: bool = False
    warm_contact_count: int = 0
    suppressed: bool = False
    suppression_reason: str | None = None

    @property
    def excluded(self) -> bool:
        return bool(self.exclusions)

    @property
    def visible(self) -> bool:
        """Whether this belongs in the match feed at all."""
        return not self.excluded and not self.suppressed

    @property
    def band(self) -> str:
        if self.score >= 80:
            return "strong"
        if self.score >= 60:
            return "moderate"
        return "weak"

    def explain(self) -> str:
        """The one-line breakdown shown on the job card.

        Reads like the brief's example: 'Stadium +25, District cooling +20,
        Riyadh +10, Director-level title +15, FM primary −30 = 40'.
        """
        if not self.components:
            return f"No signals fired = {self.score}"
        body = ", ".join(str(c) for c in self.components)
        if self.raw_score != self.score:
            return f"{body} = {self.raw_score}, capped at {self.score}"
        return f"{body} = {self.score}"


# Generic seniority markers, used when no lane title matches exactly but the
# role is plainly senior. Kept narrow on purpose — "manager" alone is not
# seniority in this market.
_SENIORITY_MARKERS = (
    "director", "head of", "general manager", "vice president",
    "chief", "executive director", "managing director", "deputy gm",
)
_SENIORITY_MARKERS_AR = ("مدير عام", "الرئيس التنفيذي", "نائب الرئيس", "مدير تنفيذي")


class ScoringEngine:
    """Scores a posting against a profile dict loaded from YAML or the database.

    Construct once per scan and reuse — the regex compilation in __init__ is the
    expensive part and the object is stateless with respect to scoring.
    """

    def __init__(self, profile: dict[str, Any]) -> None:
        self.profile = profile
        self.thresholds = profile.get("thresholds", {})
        self.salary_cfg = profile.get("salary", {})
        self.warm_cfg = profile.get("warm_route", {})
        self.tier_bonus = profile.get("employer_tier_bonus", {})

        self._signals = [self._compile_rule(s) for s in profile.get("signals", [])]
        self._exclusions = [
            self._compile_rule(e) for e in profile.get("exclusions", [])
        ]
        self._lanes = self._compile_lanes(profile.get("lanes", {}))
        self._employers = self._compile_employers(profile.get("employers", {}))
        self._seniority = [
            _keyword_pattern(m) for m in _SENIORITY_MARKERS + _SENIORITY_MARKERS_AR
        ]
        self._title_match_weight = int(
            profile.get("title_match", {}).get("lane_title", 20)
        )
        self._seniority_weight = int(
            profile.get("title_match", {}).get("seniority_generic", 10)
        )

    # -- compilation ---------------------------------------------------------

    @staticmethod
    def _compile_rule(rule: dict[str, Any]) -> dict[str, Any]:
        keywords = list(rule.get("keywords") or []) + list(rule.get("keywords_ar") or [])
        return {
            "id": rule["id"],
            "label": rule.get("label", rule["id"]),
            "weight": int(rule.get("weight", 0)),
            "fields": tuple(rule.get("fields") or ("title", "description")),
            "group": rule.get("group"),
            "flag": rule.get("flag"),
            "suppressed_by_employer_exception": bool(
                rule.get("suppressed_by_employer_exception")
            ),
            "patterns": [(kw, _keyword_pattern(kw)) for kw in keywords if str(kw).strip()],
        }

    @staticmethod
    def _compile_lanes(lanes: dict[str, Any]) -> list[dict[str, Any]]:
        compiled = []
        for lane_key, cfg in lanes.items():
            titles = list(cfg.get("titles") or []) + list(cfg.get("titles_ar") or [])
            compiled.append({
                "key": lane_key,
                "label": cfg.get("label", lane_key),
                # Longest title first so "MEP Operations Director" wins over
                # "Operations Director" when both are present.
                "patterns": sorted(
                    ((t, _keyword_pattern(t)) for t in titles),
                    key=lambda pair: len(pair[0]),
                    reverse=True,
                ),
            })
        return compiled

    @staticmethod
    def _compile_employers(employers: dict[str, Any]) -> list[dict[str, Any]]:
        compiled = []
        for lane_key, group in employers.items():
            if lane_key == "consultancy_exception":
                for entry in group or []:
                    compiled.append({
                        "lane": None, "tier": 2, "exception": True,
                        "name": entry["name"],
                        "patterns": [
                            _keyword_pattern(n)
                            for n in [entry["name"]] + list(entry.get("aliases") or [])
                        ],
                    })
                continue
            for tier_key, entries in (group or {}).items():
                tier = int(tier_key.rsplit("_", 1)[-1])
                for entry in entries or []:
                    compiled.append({
                        "lane": lane_key, "tier": tier, "exception": False,
                        "name": entry["name"],
                        "patterns": [
                            _keyword_pattern(n)
                            for n in [entry["name"]] + list(entry.get("aliases") or [])
                        ],
                    })
        return compiled

    # -- matching helpers ----------------------------------------------------

    @staticmethod
    def _haystack(posting: JobPosting, fields: Sequence[str]) -> str:
        return normalize(posting.searchable(fields))

    @staticmethod
    def _matches(rule: dict[str, Any], haystack: str) -> list[str]:
        """Every distinct keyword of this rule present in the text.

        Returned for display — the signal itself fires once regardless of how
        many keywords hit, because repetition in an advert is not evidence.
        """
        hits = [kw for kw, pattern in rule["patterns"] if pattern.search(haystack)]
        # Deterministic and de-duplicated, preserving profile order.
        seen: set[str] = set()
        return [kw for kw in hits if not (kw in seen or seen.add(kw))]

    def _identify_employer(self, posting: JobPosting) -> dict[str, Any] | None:
        haystack = normalize(f"{posting.employer}\n{posting.title}")
        for entry in self._employers:
            if any(p.search(haystack) for p in entry["patterns"]):
                return entry
        return None

    def _identify_lane(self, posting: JobPosting) -> tuple[str | None, str | None, list[str]]:
        title = normalize(posting.title)
        for lane in self._lanes:
            for raw, pattern in lane["patterns"]:
                if pattern.search(title):
                    return lane["key"], lane["label"], [raw]
        return None, None, []

    # -- the scorer ----------------------------------------------------------

    def score(self, posting: JobPosting, warm_contact_count: int = 0) -> ScoreResult:
        employer = self._identify_employer(posting)
        lane_key, lane_label, lane_hits = self._identify_lane(posting)

        # An employer on the target list disambiguates a title that matched no
        # lane — a "Delivery Director" at Nesma is still Lane A work.
        if lane_key is None and employer and employer["lane"]:
            lane_key = employer["lane"]
            lane_label = next(
                (l["label"] for l in self._lanes if l["key"] == lane_key), lane_key
            )

        components: list[ScoreComponent] = []
        flags: list[str] = []

        # Hard exclusions first — no point scoring a job he legally cannot hold.
        exclusions: list[Exclusion] = []
        for rule in self._exclusions:
            hits = self._matches(rule, self._haystack(posting, rule["fields"]))
            if hits:
                exclusions.append(
                    Exclusion(rule["id"], rule["label"], tuple(hits))
                )

        # Title and seniority.
        if lane_hits:
            components.append(ScoreComponent(
                "lane_title", f"{lane_label} title match",
                self._title_match_weight, tuple(lane_hits),
            ))
        else:
            title = normalize(posting.title)
            if any(p.search(title) for p in self._seniority):
                components.append(ScoreComponent(
                    "seniority_generic", "Senior title", self._seniority_weight,
                ))

        # Signals. Location signals are a mutually exclusive group: a posting is
        # in one city, so only the highest-weighted location match may fire.
        grouped: dict[str, ScoreComponent] = {}
        is_exception_employer = bool(employer and employer["exception"])

        for rule in self._signals:
            if rule["suppressed_by_employer_exception"] and is_exception_employer:
                continue
            hits = self._matches(rule, self._haystack(posting, rule["fields"]))
            if not hits:
                continue
            component = ScoreComponent(
                rule["id"], rule["label"], rule["weight"], tuple(hits)
            )
            if rule["flag"]:
                flags.append(rule["flag"])
            group = rule["group"]
            if group:
                incumbent = grouped.get(group)
                if incumbent is None or component.contribution > incumbent.contribution:
                    grouped[group] = component
            else:
                components.append(component)
        components.extend(grouped.values())

        # Employer tier.
        employer_tier = employer["tier"] if employer else None
        if employer_tier is not None:
            bonus = int(self.tier_bonus.get(f"tier_{employer_tier}", 0))
            if bonus:
                components.append(ScoreComponent(
                    "employer_tier", f"Tier {employer_tier} target employer",
                    bonus, (employer["name"],),
                ))

        # Salary, when the posting actually states one. Silence is not a signal.
        below = self.salary_cfg.get("below_target_threshold")
        if posting.salary_max is not None and below is not None:
            currency = (posting.salary_currency or "").upper()
            if currency in ("", self.salary_cfg.get("currency", "SAR")):
                if posting.salary_max < int(below):
                    components.append(ScoreComponent(
                        "below_target_salary",
                        f"Below target salary ({posting.salary_max:,} < {int(below):,})",
                        int(self.salary_cfg.get("below_target_penalty", -15)),
                    ))
                    flags.append("below_target_salary")

        # Warm route — the uplift that pins a known-contact job above a cold one.
        warm = warm_contact_count > 0
        if warm:
            uplift = int(self.warm_cfg.get("uplift", 15))
            label = self.warm_cfg.get("label", "Warm route available")
            plural = "s" if warm_contact_count != 1 else ""
            components.append(ScoreComponent(
                "warm_route", f"{label} ({warm_contact_count} contact{plural})", uplift,
            ))

        # Positives first, then negatives by magnitude. Deterministic, and it
        # reads the way a person would summarise it out loud.
        components.sort(
            key=lambda c: (c.contribution < 0, -c.contribution, c.signal_id)
        )

        raw = sum(c.contribution for c in components)
        score = max(0, min(100, raw))

        result = ScoreResult(
            raw_score=raw,
            score=score,
            lane=lane_key,
            lane_label=lane_label,
            employer_tier=employer_tier,
            components=components,
            exclusions=exclusions,
            flags=sorted(set(flags)),
            warm_route=warm,
            warm_contact_count=warm_contact_count,
        )

        # Facilities management is de-prioritised, not banned: an FM role that
        # still clears the high bar carries real delivery scope and should be
        # seen. Below the bar it is suppressed, with the reason recorded.
        if any(c.signal_id == "fm_primary" for c in components):
            floor = int(self.thresholds.get("fm_rescue_floor", 75))
            if score < floor:
                result.suppressed = True
                result.suppression_reason = (
                    f"Facilities management role scoring {score}, below the "
                    f"FM bar of {floor}"
                )

        return result


def score_all(
    engine: ScoringEngine,
    postings: Iterable[JobPosting],
    warm_counts: dict[str, int] | None = None,
) -> list[tuple[JobPosting, ScoreResult]]:
    """Score a batch, ordered for the feed.

    Ordering uses the uncapped raw score. A strong Riyadh stadium role can total
    well over 100 and several will display as 100; ranking on the displayed
    number would flatten them into an alphabetical list and lose the ordering
    that makes the feed worth reading.

    Warm routes outrank equivalently scored cold jobs, which is the whole point
    of section 8 — the ordering, not just the badge.
    """
    warm_counts = warm_counts or {}
    scored = [
        (p, engine.score(p, warm_counts.get(p.fingerprint, 0))) for p in postings
    ]
    scored.sort(
        key=lambda pair: (
            # Score first: the +15 uplift is what lifts a warm job, so a weak
            # warm route must not leapfrog a genuinely better cold one. Warm
            # then breaks ties, which is the "equivalently scored" case.
            -pair[1].raw_score,
            not pair[1].warm_route,
            pair[0].employer.lower(),
            pair[0].title.lower(),
        )
    )
    return scored
