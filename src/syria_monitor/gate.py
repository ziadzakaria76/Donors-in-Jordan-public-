"""The universal country check.

Every portal's records pass through this one function. It is deliberately NOT a
per-module decision: a new portal added without calling it would silently ship
worldwide notices, which is how a Caribbean education project ended up leading a
live report in a previous build.

The World Bank's `country` request parameter is silently ignored -- it returns
HTTP 200 and worldwide notices, with no error and no warning -- so this check
runs over the records AFTER fetching, unconditionally, for every portal
including ones whose API claims to filter by country.

The obvious client-side implementation also fails. `qterm` is a full-text
search, so every notice it returns contains the search word somewhere in its
indexed text; if that same indexed body is stored as the record description, a
text filter re-reads the exact field the API already matched and cannot reject
anything. Defence in depth is not depth when both layers read the same field.
Hence: the verdict is read from the country FIELD, and text is consulted only
where there is no country field at all -- and then only over fields a portal has
declared safe, never over an API-matched body.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .classify import Classifier
from .matching import ACCEPT, REJECT, CountryMatcher

# A record may set this to the list of field names that are safe to text-match.
# Anything not listed is assumed to be an API-matched body and is not consulted.
SAFE_TEXT_FIELDS = "_safe_text_fields"
DEFAULT_SAFE_FIELDS = ("title", "notice_title", "project_name")


@dataclass
class GateStats:
    seen: int = 0
    accepted_by_field: int = 0
    accepted_by_text: int = 0
    rejected_by_field: int = 0
    rejected_no_evidence: int = 0
    link_types: dict = field(default_factory=dict)

    def note(self, link_type: str) -> None:
        self.link_types[link_type] = self.link_types.get(link_type, 0) + 1


class CountryGate:
    def __init__(self, profile: dict, matcher: Optional[CountryMatcher] = None,
                 classifier: Optional[Classifier] = None):
        self.profile = profile
        self.matcher = matcher or CountryMatcher(profile)
        self.classifier = classifier or Classifier(profile, self.matcher)

    def safe_text(self, record: dict) -> str:
        names = record.get(SAFE_TEXT_FIELDS) or DEFAULT_SAFE_FIELDS
        return " \n ".join(str(record[n]) for n in names if record.get(n))

    def check(self, record: dict, stats: Optional[GateStats] = None) -> tuple[bool, str, Optional[str]]:
        """Return (keep, syria_link_type, delivery_country) for one raw record."""
        stats = stats or GateStats()
        stats.seen += 1

        verdict = self.matcher.country_verdict(record)
        if verdict is REJECT:
            stats.rejected_by_field += 1
            link_type, delivery = self.classifier.classify(record, self.safe_text(record))
            stats.note(link_type)
            return False, link_type, delivery

        if verdict is ACCEPT:
            stats.accepted_by_field += 1
        else:
            # No country field anywhere: only now may text decide, and only over
            # fields the portal declared safe.
            if not self.matcher.matches_text(self.safe_text(record)):
                stats.rejected_no_evidence += 1
                stats.note("unclassified")
                return False, "unclassified", None
            stats.accepted_by_text += 1

        link_type, delivery = self.classifier.classify(record, self.safe_text(record))
        stats.note(link_type)
        return True, link_type, delivery
