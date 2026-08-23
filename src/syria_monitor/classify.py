"""Delivery-location classification -> syria_link_type.

The biggest false-positive class in this build is not a place name: it is
"Syrian refugees" in a tender delivered in Jordan, Lebanon, Turkiye, Iraq or
Egypt. There are thousands of them and they will swamp a genuine Syria pipeline
if beneficiary nationality is treated as country of implementation.

So: classify against the DELIVERY LOCATION, and where a notice states both, the
delivery location wins. The verdict is carried on the record as syria_link_type
rather than collapsed into a boolean, so a wrong call is visible in the report
instead of silent.
r"""

from __future__ import annotations

import re
from typing import Optional

from .matching import CountryMatcher, ACCEPT, REJECT
from .models import (CROSS_BORDER, INSIDE, REFUGEE_HOSTING, REGIONAL, UNCLASSIFIED)


def _compile(terms) -> list[re.Pattern]:
    return [re.compile(r"(?<!\w)" + re.escape(t) + r"(?!\w)", re.IGNORECASE) for t in terms]


class Classifier:
    def __init__(self, profile: dict, matcher: Optional[CountryMatcher] = None):
        self.profile = profile
        self.matcher = matcher or CountryMatcher(profile)
        self.iso2 = (profile.get("iso2") or "").upper()

        self._hubs = [(h["country"], _compile(h.get("variants", [])))
                      for h in profile.get("hub_locations", [])]
        self._neighbours = {iso: _compile(names)
                            for iso, names in (profile.get("neighbour_names") or {}).items()}
        self._beneficiary = _compile(profile.get("beneficiary_terms", []))
        self._hosting = set(profile.get("refugee_hosting_countries", []))

    # ------------------------------------------------------------------ util
    def _countries_in_fields(self, record: dict) -> tuple[set[str], list[str]]:
        """ISO2 codes named by the record's own country fields, plus any foreign
        country names it states that are not in our neighbour table.

        The second half matters: a record whose country field says "Malawi"
        names a country we have no ISO mapping for, and treating that as "no
        delivery field stated" would drop it through to the text fallback --
        where "experience in Syria an advantage" would classify it as ours.
        That is exactly the failure that put a Caribbean education project at
        the top of a live report.
        """
        found: set[str] = set()
        foreign: list[str] = []
        for name in self.matcher.field_names():
            if name not in record:
                continue
            value = record.get(name)
            values = list(value) if isinstance(value, (list, tuple, set)) else [value]
            while values:
                item = values.pop()
                if isinstance(item, dict):
                    values.extend(item.values())
                    continue
                if isinstance(item, (list, tuple, set)):
                    values.extend(item)
                    continue
                if item is None or not str(item).strip():
                    continue
                text = str(item).strip()
                verdict = self.matcher._field_says(text)
                if verdict is ACCEPT:
                    found.add(self.iso2)
                    continue
                matched_neighbour = False
                for iso, pats in self._neighbours.items():
                    if text.upper() == iso or any(p.search(text) for p in pats):
                        found.add(iso)
                        matched_neighbour = True
                if not matched_neighbour and verdict is REJECT:
                    foreign.append(text)
        return found, foreign

    def _countries_in_text(self, text: str) -> set[str]:
        found = set()
        for iso, pats in self._neighbours.items():
            if any(p.search(text) for p in pats):
                found.add(iso)
        return found

    def _hub_countries(self, text: str) -> set[str]:
        return {iso for iso, pats in self._hubs if any(p.search(text) for p in pats)}

    def mentions_beneficiaries(self, text: str) -> bool:
        return any(p.search(text) for p in self._beneficiary)

    # -------------------------------------------------------------- classify
    def classify(self, record: dict, *texts: Optional[str]) -> tuple[str, Optional[str]]:
        """Return (syria_link_type, delivery_country).r"""
        blob = " \n ".join(t for t in texts if t)
        field_countries, foreign_names = self._countries_in_fields(record)
        ours_in_field = self.iso2 in field_countries
        others_in_field = field_countries - {self.iso2}
        states_other = bool(others_in_field or foreign_names)

        # Delivery location wins wherever the record states one.
        if ours_in_field:
            return (REGIONAL if states_other else INSIDE), self.iso2

        if states_other:
            hubs = self._hub_countries(blob)
            has_country_evidence = self.matcher.evidence(blob).matched
            if hubs & others_in_field and has_country_evidence and not self.mentions_beneficiaries(blob):
                return CROSS_BORDER, sorted(others_in_field)[0]
            if others_in_field & self._hosting and has_country_evidence:
                return REFUGEE_HOSTING, sorted(others_in_field)[0]
            # A stated delivery country that is neither ours, a hub, nor a host
            # is not our tender, whatever the description happens to mention.
            fallback = sorted(others_in_field)[0] if others_in_field else foreign_names[0]
            return UNCLASSIFIED, fallback

        # No country field at all: only now may text decide.
        if not self.matcher.evidence(blob).matched:
            return UNCLASSIFIED, None

        text_countries = self._countries_in_text(blob)
        hubs = self._hub_countries(blob)
        if hubs:
            return CROSS_BORDER, sorted(hubs)[0]
        if text_countries & self._hosting:
            if self.mentions_beneficiaries(blob):
                return REFUGEE_HOSTING, sorted(text_countries & self._hosting)[0]
            return REGIONAL, self.iso2
        if self.mentions_beneficiaries(blob) and not self._names_our_place(blob):
            return REFUGEE_HOSTING, None
        return INSIDE, self.iso2

    def _names_our_place(self, text: str) -> bool:
        """True when the text names one of our own places, not just the country."""
        ev = self.matcher.evidence(text)
        places = {p.get("canonical") for p in self.profile.get("places", [])}
        return any(term in places for term in ev.strong + ev.weak)
