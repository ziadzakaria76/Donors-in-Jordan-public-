"""Sanctions and counterparty screening.

Decision support, never legal advice. This module flags possible matches for a
human to check; it never clears anyone, and the word "clear" appears in no
output it produces. Every report states the fetch date of each list, because a
stale sanctions list that looks current is worse than no screening at all.

Screening is advisory here by configuration: hits are flagged, never used to
exclude a tender.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

DISCLAIMER = ("Sanctions screening output is a triage aid, never legal clearance. "
              "No counterparty is reported as clear. Verify against the official "
              "lists before acting.")

SOURCES = {
    "ofac_sdn": {
        "label": "OFAC SDN",
        "url": "https://sanctionslistservice.ofac.treas.gov/api/download/sdn.csv",
        "format": "csv",
        "name_column": 1,
    },
    "eu_consolidated": {
        "label": "EU consolidated",
        "url": ("https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/"
                "content?token=dG9rZW4tMjAxNw"),
        "format": "csv_semicolon",
        "name_column": None,
    },
    "uk_ofsi": {
        "label": "UK OFSI consolidated",
        "url": "https://assets.publishing.service.gov.uk/media/consolidated-list.csv",
        "format": "csv",
        "name_column": None,
    },
}

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")


class ScreeningUnavailable(RuntimeError):
    """Raised when a list cannot be loaded.

    An empty or failed download must fail loudly: screening everything clean is
    the one outcome this module must never produce.
    """


def normalise(name: str) -> str:
    return _SPACE.sub(" ", _PUNCT.sub(" ", (name or "").lower())).strip()


@dataclass
class SanctionsList:
    key: str
    label: str
    fetched: Optional[date]
    names: set[str] = field(default_factory=set)
    error: Optional[str] = None

    @property
    def usable(self) -> bool:
        return bool(self.names)

    @property
    def age_days(self) -> Optional[int]:
        return (date.today() - self.fetched).days if self.fetched else None


@dataclass
class Hit:
    party: str
    matched_name: str
    list_key: str
    list_label: str
    list_fetched: Optional[str]

    def as_dict(self) -> dict:
        return {"party": self.party, "matched_name": self.matched_name,
                "list": self.list_label, "list_fetched": self.list_fetched,
                "note": DISCLAIMER}


class Screener:
    def __init__(self, cache_dir: Path, fetcher=None, max_age_days: int = 7):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.fetcher = fetcher
        self.max_age_days = max_age_days
        self.lists: dict[str, SanctionsList] = {}

    # ------------------------------------------------------------------ lists
    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def load_cached(self, key: str) -> Optional[SanctionsList]:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None
        fetched = datetime.fromisoformat(blob["fetched"]).date() if blob.get("fetched") else None
        return SanctionsList(key=key, label=blob.get("label", key), fetched=fetched,
                             names=set(blob.get("names") or []))

    def save_cached(self, sanctions: SanctionsList) -> None:
        self._cache_path(sanctions.key).write_text(json.dumps({
            "label": sanctions.label,
            "fetched": sanctions.fetched.isoformat() if sanctions.fetched else None,
            "names": sorted(sanctions.names),
        }), encoding="utf-8")

    def refresh(self, key: str) -> SanctionsList:
        source = SOURCES[key]
        if self.fetcher is None:
            raise ScreeningUnavailable(f"{source['label']}: no fetcher configured")
        response = self.fetcher.get(source["url"])
        if not response.ok or not response.text.strip():
            raise ScreeningUnavailable(
                f"{source['label']}: HTTP {response.status}, {len(response.text)} bytes")
        names = parse_names(response.text, source)
        if not names:
            raise ScreeningUnavailable(f"{source['label']}: downloaded but parsed 0 names")
        sanctions = SanctionsList(key=key, label=source["label"], fetched=date.today(), names=names)
        self.save_cached(sanctions)
        return sanctions

    def load(self, keys: Optional[Iterable[str]] = None) -> dict[str, SanctionsList]:
        for key in (keys or SOURCES):
            cached = self.load_cached(key)
            fresh_enough = cached and cached.age_days is not None and cached.age_days <= self.max_age_days
            if fresh_enough:
                self.lists[key] = cached
                continue
            try:
                self.lists[key] = self.refresh(key)
            except Exception as exc:
                if cached and cached.usable:
                    cached.error = f"refresh failed, using cache from {cached.fetched}: {exc}"
                    self.lists[key] = cached
                else:
                    self.lists[key] = SanctionsList(key=key, label=SOURCES[key]["label"],
                                                    fetched=None, error=str(exc))
        return self.lists

    # --------------------------------------------------------------- screening
    def screen(self, parties: Iterable[Optional[str]]) -> list[dict]:
        """Flag possible matches. Never returns a verdict of 'clear'."""
        usable = [s for s in self.lists.values() if s.usable]
        if not usable:
            raise ScreeningUnavailable(
                "no sanctions list could be loaded -- screening produced no result. "
                "This is reported as an error, not as a clean screen.")
        hits: list[Hit] = []
        for party in parties:
            party_norm = normalise(party or "")
            if not party_norm or len(party_norm) < 4:
                continue
            party_tokens = set(party_norm.split())
            for sanctions in usable:
                for entry in sanctions.names:
                    if _is_match(party_norm, party_tokens, entry):
                        hits.append(Hit(party=party or "", matched_name=entry,
                                        list_key=sanctions.key, list_label=sanctions.label,
                                        list_fetched=sanctions.fetched.isoformat()
                                        if sanctions.fetched else None))
                        break
        return [h.as_dict() for h in hits]

    def list_status(self) -> list[dict]:
        return [{"list": s.label, "fetched": s.fetched.isoformat() if s.fetched else None,
                 "names": len(s.names), "error": s.error} for s in self.lists.values()]


def _is_match(party_norm: str, party_tokens: set[str], entry: str) -> bool:
    """Strict matching only.

    Exact normalised equality, or full containment of a multi-token designated
    name inside the party name. Fuzzy/phonetic matching is deliberately NOT
    enabled by default: "Ahmad" and "Ahmed" are different people, and a silent
    near-match is worse than no match because it reads as a finding.
    """
    if party_norm == entry:
        return True
    entry_tokens = entry.split()
    if len(entry_tokens) >= 2 and set(entry_tokens) <= party_tokens:
        return True
    return False


def parse_names(text: str, source: dict) -> set[str]:
    delimiter = ";" if source.get("format") == "csv_semicolon" else ","
    names: set[str] = set()
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return names

    header = [h.strip().lower() for h in rows[0]]
    name_columns = [i for i, h in enumerate(header)
                    if h in ("name", "sdn_name", "wholename", "name1", "namealias_wholename",
                             "full name", "fullname", "entity name")]
    fixed = source.get("name_column")
    start = 1 if name_columns else 0

    for row in rows[start:]:
        if not row:
            continue
        candidates = []
        if name_columns:
            candidates = [row[i] for i in name_columns if i < len(row)]
        elif isinstance(fixed, int) and fixed < len(row):
            candidates = [row[fixed]]
        else:
            candidates = [max(row, key=len)] if row else []
        for candidate in candidates:
            norm = normalise(candidate)
            if len(norm) >= 4 and norm not in ("name", "-0-", "unknown"):
                names.add(norm)
    return names
