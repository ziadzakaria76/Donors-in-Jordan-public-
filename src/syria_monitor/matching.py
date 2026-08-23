"""Country matching.

Driven entirely by a profile: no country name appears in this file.

Two things here are load-bearing and easy to "simplify" into a bug:

1.  Latin terms are ENUMERATED and each matched with (?<!\w)term(?!\w), rather
    than covered by one clever pattern. Tested behaviour of the alternatives:

        pattern         Syria   Syrian Arab Republic   Assyrian   Syriac
        \bsyria\b       match   MISS                   rejected   rejected
        \bsyria\w*\b    match   match                  rejected   FALSE MATCH
        \bsyrian?\b     match   match                  rejected   rejected

    \bsyria\b looks like the careful choice and silently misses the formal UN
    name — which is the spelling the World Bank uses, i.e. the most valuable
    source in the build. Adding a wildcard to fix that re-admits "Syriac"
    (Syriac Orthodox, Syriac Catholic, the Syriac language), which appears in
    minority-rights and heritage tenders across Iraq, Turkiye, Lebanon and
    Sweden. All four rows are in the test suite.

2.  Arabic is matched as a SUBSTRING, never with word boundaries. Arabic is
    agglutinative, so the stem carries prefixes and suffixes directly:
        سوري  matches سورية، السورية، السوري، سوريا، الجمهورية العربية السورية
        سوريا matches only itself and misses the formal Arabic country name
    It still rejects آشوري and سرياني, which use different root letters.
    Do not port the Latin word-boundary logic onto Arabic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

# A country field naming another country is a rejection; a country field naming
# ours is an acceptance that text is not allowed to overturn; no country field
# at all is the only case where text matching gets a say.
ACCEPT, REJECT, UNKNOWN = True, False, None

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")


def _term_pattern(term: str) -> re.Pattern:
    """(?<!\w)term(?!\w) — word-ish boundaries that also work for multiword terms.

    \b would do here, but (?<!\w)/(?!\w) states the intent directly and behaves
    identically for terms that start or end with a non-word character.
    """
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)


@dataclass
class Evidence:
    """What a piece of text said about the country, and how strongly."""

    strong: list[str] = field(default_factory=list)
    weak: list[str] = field(default_factory=list)
    disqualified: list[str] = field(default_factory=list)

    @property
    def matched(self) -> bool:
        # One strong signal is enough. A single weak signal (a place name that
        # also exists elsewhere) is not: SAM.gov and UK Find a Tender scan whole
        # national corpora, so a bare "Damascus" would pull in US municipal
        # contracts. Two independent weak signals corroborate each other.
        return bool(self.strong) or len(self.weak) >= 2

    def summary(self) -> list[str]:
        out = [f"strong:{t}" for t in self.strong] + [f"weak:{t}" for t in self.weak]
        out += [f"disqualified:{t}" for t in self.disqualified]
        return out


class CountryMatcher:
    """Profile-driven country matcher. Holds no country knowledge of its own."""

    def __init__(self, profile: dict):
        self.profile = profile
        self.iso2 = (profile.get("iso2") or "").upper()
        self.iso3 = (profile.get("iso3") or "").upper()

        self._strong = [(t, _term_pattern(t)) for t in profile.get("strong_terms", [])]
        self._arabic = list(profile.get("arabic_stems", []))
        self._negative = [(t, _term_pattern(t)) for t in profile.get("negative_terms", [])]
        self._disqualifiers = [re.compile(p, re.IGNORECASE)
                               for p in profile.get("place_disqualifiers", [])]

        self._places_strong: list[tuple[str, re.Pattern]] = []
        self._places_weak: list[tuple[str, re.Pattern]] = []
        for place in profile.get("places", []):
            canonical = place.get("canonical", "")
            bucket = self._places_weak if place.get("ambiguous") else self._places_strong
            for variant in place.get("variants", []):
                bucket.append((canonical, _term_pattern(variant)))

        tld = profile.get("tld")
        # Require a non-word char after the TLD so "ministry.system" does not
        # match. .sy is short enough to be a genuine hazard in a way .jo is not.
        self._tld_re = re.compile(r"\.%s(?!\w)" % re.escape(tld), re.IGNORECASE) if tld else None

    # ------------------------------------------------------------------ text
    def evidence(self, *texts: Optional[str]) -> Evidence:
        """Weigh free text. Never call this on a record that has a country field."""
        ev = Evidence()
        raw = " \n ".join(t for t in texts if t)
        if not raw.strip():
            return ev

        # A contact address at a donor's in-country office would otherwise make
        # every notice on that page look country-related, so addresses are
        # stripped before term matching — but a country-code TLD is a deliberate
        # country signal and is kept as positive evidence. Match it both inside
        # a URL and as bare text (e.g. mopic.gov.sy).
        if self._tld_re:
            for chunk in _EMAIL_RE.findall(raw) + _URL_RE.findall(raw) + [raw]:
                if self._tld_re.search(chunk):
                    ev.strong.append(f"tld:.{self.profile.get('tld')}")
                    break

        text = _URL_RE.sub(" ", _EMAIL_RE.sub(" ", raw))

        # Remove negatives before matching so they can never contribute
        # evidence. The boundary rules already reject them; this makes the
        # intent explicit and gives the tests something to assert on.
        for term, pat in self._negative:
            if pat.search(text):
                ev.disqualified.append(term)
                text = pat.sub(" ", text)

        for term, pat in self._strong:
            if pat.search(text):
                ev.strong.append(term)

        for stem in self._arabic:
            if stem in text:                      # substring by design
                ev.strong.append(f"ar:{stem}")

        for canonical, pat in self._places_strong:
            if pat.search(text) and canonical not in ev.strong:
                ev.strong.append(canonical)

        for canonical, pat in self._places_weak:
            if not pat.search(text):
                continue
            if any(d.search(text) for d in self._disqualifiers):
                ev.disqualified.append(f"place:{canonical}")
            elif canonical not in ev.weak:
                ev.weak.append(canonical)

        return ev

    def matches_text(self, *texts: Optional[str]) -> bool:
        return self.evidence(*texts).matched

    # ----------------------------------------------------------------- field
    def field_names(self, extra: Iterable[str] = ()) -> list[str]:
        base = ["project_ctry_name", "countryshortname", "country_name", "countryname",
                "cty_name", "country", "project_country", "delivery_country",
                "place_of_performance_country", "place-of-performance-country",
                "place-of-performance-country-lot", "ncode"]
        return base + [e for e in extra if e not in base]

    def _field_says(self, value: Any) -> Optional[bool]:
        """ACCEPT / REJECT / UNKNOWN for a single country-field value."""
        if value is None:
            return UNKNOWN
        if isinstance(value, dict):
            # TED returns multilingual maps like {'eng': [...]}.
            values = [v for sub in value.values() for v in (sub if isinstance(sub, list) else [sub])]
            return self._field_says(values)
        if isinstance(value, (list, tuple, set)):
            verdicts = [self._field_says(v) for v in value]
            if ACCEPT in verdicts:
                return ACCEPT
            if REJECT in verdicts:
                return REJECT
            return UNKNOWN

        text = str(value).strip()
        if not text:
            return UNKNOWN

        upper = text.upper()
        if upper in (self.iso2, self.iso3):
            return ACCEPT
        # An ISO code is only trusted when it IS the whole field value; a bare
        # "SY" inside prose is far too short to be evidence.
        for _term, pat in self._strong:
            if pat.search(text):
                return ACCEPT
        if any(stem in text for stem in self._arabic):
            return ACCEPT
        for canonical, pat in self._places_strong:
            if pat.search(text):
                return ACCEPT
        return REJECT

    def country_verdict(self, record: dict, extra_fields: Iterable[str] = ()) -> Optional[bool]:
        """Tri-state verdict read from the country FIELD, never from the text.

        ACCEPT  — a country field names our country. Accept, and do not let a
                  text check second-guess it: "Supply of laboratory equipment,
                  Package 3" names no country and would be wrongly dropped.
        REJECT  — a country field names some other country.
        UNKNOWN — no country field at all. Only then may text decide.
        """
        seen_any = False
        for name in self.field_names(extra_fields):
            if name not in record:
                continue
            verdict = self._field_says(record.get(name))
            if verdict is ACCEPT:
                return ACCEPT
            if verdict is REJECT:
                seen_any = True
        return REJECT if seen_any else UNKNOWN
