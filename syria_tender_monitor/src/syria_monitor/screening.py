"""Sanctions and counterparty screening.

Decision support, never legal advice. This module flags possible matches for a
human to check; it never clears anyone, and the word "clear" appears in no
output it produces. Every report states the fetch date of each list, because a
stale sanctions list that looks current is worse than no screening at all.

Screening is advisory here by configuration: hits are flagged, never used to
exclude a tender.
r"""

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
    # THE LIST THIS USED TO READ NO LONGER EXISTS. OFSI's Consolidated List of
    # Asset Freeze Targets closed on 28 January 2026; from that date the UK
    # Sanctions List is the single source for UK designations. Every run before
    # this reported
    #
    #     UK OFSI consolidated: fetched None, 0 names -- HTTP 404, 5201 bytes
    #
    # and carried on screening against two lists of three.
    #
    # NOT data.gov.uk/dataset/financialsanctions, which is the obvious
    # replacement and the wrong one: that dataset IS the consolidated list, so
    # pointing at it would swap a loud 404 for a list frozen since January that
    # looks like it is working. That is strictly worse than the failure.
    #
    # NOT the GOV.UK publication page either. Resolving the download link off
    # that page was tried and shipped, and the run of 2026-08-30 reported what
    # the page actually carries:
    #
    #     What the page offers: .../SanctionsListSchema-4.33.3.xsd
    #
    # One asset link, and a schema rather than the data -- the attachment list
    # is client-rendered, so no pattern can match links that are not in the HTML.
    #
    # These are FCDO's own published addresses, and they are stable paths rather
    # than the content-addressed ones GOV.UK rehashes on every republication.
    # CSV first because the parser below reads it directly; XML is what FCDO
    # documents most prominently and is the fallback.
    #
    # NEITHER IS VERIFIED FROM HERE. sanctionslist.fcdo.gov.uk answers 403 to
    # CONNECT behind this environment's egress allowlist, as do gov.uk,
    # data.gov.uk and the artifact store. So the run is the verification: it
    # reports which URL served and how many names came back, and a name count
    # that is implausible is as visible as a failure.
    "uk_sanctions": {
        "label": "UK Sanctions List",
        "urls": (
            "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv",
            "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml",
        ),
        "format": "auto",
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
    # Which of the published addresses actually served this list. Reported, so
    # a run says where its names came from rather than leaving it to be assumed.
    source_url: Optional[str] = None

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
                             names=set(blob.get("names") or []),
                             source_url=blob.get("source_url"))

    def save_cached(self, sanctions: SanctionsList) -> None:
        self._cache_path(sanctions.key).write_text(json.dumps({
            "label": sanctions.label,
            "fetched": sanctions.fetched.isoformat() if sanctions.fetched else None,
            "source_url": sanctions.source_url,
            "names": sorted(sanctions.names),
        }), encoding="utf-8")

    def refresh(self, key: str) -> SanctionsList:
        """Download and parse a list, trying each published address in turn.

        WHICH ADDRESS SERVED IS RECORDED, not inferred. A source with several
        candidates that reports only "0 names" leaves the reader unable to tell
        a moved file from an empty one from a parser that did not understand
        the format, and this module has now produced all three.
        """
        source = SOURCES[key]
        if self.fetcher is None:
            raise ScreeningUnavailable(f"{source['label']}: no fetcher configured")

        urls = source.get("urls") or (source["url"],)
        attempts: list[str] = []
        for url in urls:
            try:
                response = self.fetcher.get(url)
            except Exception as exc:                      # transport, not HTTP
                attempts.append(f"{url}: {type(exc).__name__}: {exc}")
                continue
            body = response.text or ""
            if not response.ok or not body.strip():
                attempts.append(f"{url}: HTTP {response.status}, {len(body)} bytes")
                continue
            names = parse_names(body, source)
            if not names:
                attempts.append(f"{url}: HTTP {response.status}, {len(body)} bytes, "
                                f"parsed 0 names")
                continue
            sanctions = SanctionsList(key=key, label=source["label"],
                                      fetched=date.today(), names=names,
                                      source_url=url)
            self.save_cached(sanctions)
            return sanctions

        raise ScreeningUnavailable(
            f"{source['label']}: no address returned a usable list. "
            + " | ".join(attempts))

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
                 "names": len(s.names), "error": s.error,
                 "source_url": s.source_url} for s in self.lists.values()]


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


# Element names the UK Sanctions List XML uses for the designated party. Kept
# narrow on purpose: a tag merely CONTAINING "name" also catches NameType and
# similar metadata, which would pad the list with words like "Primary name" and
# turn every screening run into a source of false flags.
_XML_NAME_TAGS = re.compile(r"(?i)^(name\d*|wholename|fullname|lastname|firstname|"
                            r"nameofentity|organisationname)$")


def parse_xml_names(text: str) -> set[str]:
    """Designated names out of a sanctions XML document.

    THE SCHEMA IS NOT VERIFIED HERE. sanctionslist.fcdo.gov.uk cannot be reached
    from the environment this was written in, so the tag set below is what
    FCDO's published schema name and the usual shape of these documents imply,
    not what was read off the file. The run reports the count, and a count that
    is implausible for a national sanctions list says so at a glance -- which is
    the same check the two working lists already get.
    """
    from xml.etree import ElementTree

    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return set()

    names: set[str] = set()
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]          # strip any namespace
        if not _XML_NAME_TAGS.match(tag):
            continue
        value = (element.text or "").strip()
        # A designated name is a name: not a sentence, not a single letter.
        if not 2 <= len(value) <= 200:
            continue
        # NORMALISED, as the CSV path normalises. Screening compares normalised
        # forms, so a set of raw names would be a list that loads, reports a
        # plausible count, and matches nothing -- the failure this module keeps
        # producing in new shapes.
        norm = normalise(value)
        if norm:
            names.add(norm)
    return names


def parse_names(text: str, source: dict) -> set[str]:
    # A source may publish more than one format at more than one address, so the
    # document decides how it is read rather than the configuration guessing.
    stripped = text.lstrip()
    if stripped.startswith("<?xml") or stripped.startswith("<"):
        return parse_xml_names(text)
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

    # Row 0 is always treated as a header: all three published lists carry one.
    # Falling back to "longest cell in every row" without skipping it turns a
    # column heading into a designated name -- which both invents false
    # positives and hides an empty download behind a plausible-looking count.
    for row in rows[1:]:
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
