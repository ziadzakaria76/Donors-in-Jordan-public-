"""
Agent 2 -- filter, score and deduplicate.

Filter order (per spec):
  1. language
  2. closing date (expired)
  3. minimum value
  4. notice type
  5. lookback window
  6. new-only (seen_tenders.db)

Then every survivor is scored 0-100 and near-duplicate titles across portals are
merged, keeping the highest-scoring copy and annotating it with the others.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from rapidfuzz import fuzz

import config

from . import tracker

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------
def _as_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _passes_language(tender: dict) -> tuple[bool, str | None]:
    mode = config.LANGUAGE_MODE
    language = tender.get("language", "en")
    if mode == "english_only" and language != "en":
        return False, "non-English notice"
    if language == "ar":
        tender["language_flag"] = config.ARABIC_FLAG_NOTE
    return True, None


def _passes_deadline(tender: dict, today: date) -> tuple[bool, str | None]:
    if not config.EXCLUDE_CLOSED:
        return True, None
    closing = _as_date(tender.get("closing_date"))
    if closing is None:
        if config.KEEP_UNKNOWN_DEADLINE:
            tender["deadline_flag"] = "Deadline not published - verify on the portal"
            return True, None
        return False, "no deadline published"
    if closing < today:
        return False, "deadline passed"
    return True, None


def _passes_value(tender: dict) -> tuple[bool, str | None]:
    threshold = config.MIN_VALUE_USD
    if not threshold:
        return True, None
    value = tender.get("estimated_value_usd")
    if value is None:
        if config.KEEP_UNKNOWN_VALUE:
            tender["value_flag"] = "Value not published"
            return True, None
        return False, "value not published"
    if value < threshold:
        return False, f"value below USD {threshold:,.0f}"
    return True, None


def _passes_type(tender: dict) -> tuple[bool, str | None]:
    if not config.NOTICE_TYPES:
        return True, None
    notice_type = (tender.get("notice_type") or "").lower()
    if any(wanted.lower() in notice_type for wanted in config.NOTICE_TYPES):
        return True, None
    return False, "notice type excluded"


def _passes_lookback(tender: dict, today: date) -> tuple[bool, str | None]:
    if not config.LOOKBACK_DAYS:
        return True, None
    posted = _as_date(tender.get("posted_date"))
    if posted is None:
        return True, None  # never drop a tender purely for missing a posted date
    if (today - posted).days > config.LOOKBACK_DAYS:
        return False, f"posted more than {config.LOOKBACK_DAYS} days ago"
    return True, None


def apply_filters(tenders: list[dict], new_only: bool | None = None) -> tuple[list[dict], dict]:
    """Run every filter in order. Returns (kept, rejection counts)."""
    today = date.today()
    use_new_only = config.NEW_ONLY_MODE if new_only is None else new_only
    previously_seen = tracker.seen_ids() if use_new_only else set()

    kept: list[dict] = []
    rejected: dict[str, int] = {}

    def reject(reason: str) -> None:
        rejected[reason] = rejected.get(reason, 0) + 1

    for tender in tenders:
        if not tender.get("title"):
            reject("no title")
            continue

        for check in (
            lambda t: _passes_language(t),
            lambda t: _passes_deadline(t, today),
            lambda t: _passes_value(t),
            lambda t: _passes_type(t),
            lambda t: _passes_lookback(t, today),
        ):
            ok, reason = check(tender)
            if not ok:
                reject(reason or "filtered")
                break
        else:
            if use_new_only and tender["id"] in previously_seen:
                reject("already reported in a previous run")
                continue
            kept.append(tender)

    log.info("Filtering: %d in -> %d kept (%s)", len(tenders), len(kept), rejected or "no rejections")
    return kept, rejected


# --------------------------------------------------------------------------
# Eligibility
# --------------------------------------------------------------------------
def annotate_eligibility(tender: dict) -> bool:
    """Mark national-only tenders. Returns True if the tender is restricted."""
    blob = " ".join(
        str(tender.get(field) or "")
        for field in ("eligibility", "description", "title", "notice_type")
    ).lower()
    restricted = any(marker in blob for marker in config.NATIONAL_ONLY_MARKERS)
    if restricted:
        tender["eligibility_flag"] = "NATIONAL ONLY - international firms likely ineligible"
    tender["national_only"] = restricted
    return restricted


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
def _active_weights() -> dict[str, float]:
    """Drop components whose filter is disabled, then renormalise to 100."""
    weights = dict(config.SCORE_WEIGHTS)
    if not config.TARGET_SECTORS:
        # "All sectors" -- every tender would score identically, so the
        # component carries no information. Drop it.
        weights.pop("sector", None)
    total = sum(weights.values()) or 1.0
    return {name: value * 100.0 / total for name, value in weights.items()}


def _keyword_terms() -> list[str]:
    return config.MATCH_KEYWORDS or config.RANKING_LEXICON


def _keyword_hits(tender: dict, terms: list[str]) -> int:
    blob = f"{tender.get('title', '')} {tender.get('description', '')}".lower()
    return sum(1 for term in terms if term.lower() in blob)


def _sector_points(tender: dict) -> float:
    """1.0 exact sector match, 0.5 partial, 0.0 none."""
    sector = (tender.get("sector") or "").lower()
    if not sector:
        return 0.0
    targets = [s.lower() for s in config.TARGET_SECTORS]
    if sector in targets:
        return 1.0
    if any(word in sector for target in targets for word in target.split()):
        return 0.5
    return 0.0


def _value_points(tender: dict) -> float:
    """1.0 above threshold, 0.53 (8/15) unknown, 0.0 below."""
    value = tender.get("estimated_value_usd")
    if value is None:
        return 8.0 / 15.0
    if not config.MIN_VALUE_USD or value >= config.MIN_VALUE_USD:
        return 1.0
    return 0.0


def _urgency_points(tender: dict, today: date) -> float:
    """15 within 14 days, 10 within 30, 5 within 60, 2 beyond, 0 unknown."""
    closing = _as_date(tender.get("closing_date"))
    if closing is None:
        return 0.0
    days = (closing - today).days
    tender["days_to_deadline"] = days
    if days < 0:
        return 0.0
    if days <= 14:
        return 1.0
    if days <= 30:
        return 10.0 / 15.0
    if days <= 60:
        return 5.0 / 15.0
    return 2.0 / 15.0


def score_tenders(tenders: list[dict]) -> list[dict]:
    """Score each tender 0-100 and attach a per-component breakdown."""
    if not tenders:
        return []

    today = date.today()
    weights = _active_weights()
    terms = _keyword_terms()

    hits = {t["id"]: _keyword_hits(t, terms) for t in tenders}
    max_hits = max(hits.values()) or 1

    for tender in tenders:
        annotate_eligibility(tender)

        components: dict[str, float] = {}
        if "keyword" in weights:
            components["keyword"] = round(
                weights["keyword"] * hits[tender["id"]] / max_hits, 1
            )
        if "sector" in weights:
            components["sector"] = round(weights["sector"] * _sector_points(tender), 1)
        if "value" in weights:
            components["value"] = round(weights["value"] * _value_points(tender), 1)
        if "urgency" in weights:
            components["urgency"] = round(weights["urgency"] * _urgency_points(tender, today), 1)

        score = sum(components.values())
        if tender.get("national_only") and config.ELIGIBILITY_MODE == "flag":
            components["eligibility_penalty"] = -float(config.NATIONAL_ONLY_PENALTY)
            score -= config.NATIONAL_ONLY_PENALTY

        tender["keyword_hits"] = hits[tender["id"]]
        tender["score_components"] = components
        tender["score"] = round(max(0.0, min(100.0, score)), 1)

    tenders.sort(key=lambda t: t["score"], reverse=True)
    for rank, tender in enumerate(tenders, start=1):
        tender["rank"] = rank
    return tenders


# --------------------------------------------------------------------------
# Deduplication
# --------------------------------------------------------------------------
def deduplicate(tenders: list[dict]) -> tuple[list[dict], int]:
    """Merge near-identical titles across portals, keeping the best-scoring copy."""
    if len(tenders) < 2:
        return tenders, 0

    ordered = sorted(tenders, key=lambda t: t.get("score", 0), reverse=True)
    kept: list[dict] = []
    merged = 0

    for tender in ordered:
        match = None
        for candidate in kept:
            similarity = fuzz.token_sort_ratio(
                tender.get("title", ""), candidate.get("title", "")
            )
            if similarity >= config.DEDUPE_SIMILARITY_THRESHOLD:
                match = candidate
                break
        if match is None:
            kept.append(tender)
            continue

        merged += 1
        also = match.setdefault("also_found_on", [])
        if tender["portal"] != match["portal"] and tender["portal"] not in also:
            also.append(tender["portal"])
        # Prefer any field the winning copy is missing
        for field in ("closing_date", "estimated_value_usd", "contact", "eligibility", "url"):
            if not match.get(field) and tender.get(field):
                match[field] = tender[field]

    for tender in kept:
        if tender.get("also_found_on"):
            tender["duplicate_note"] = "Also found on: " + ", ".join(tender["also_found_on"])

    kept.sort(key=lambda t: t.get("score", 0), reverse=True)
    for rank, tender in enumerate(kept, start=1):
        tender["rank"] = rank

    log.info("Deduplication: %d merged, %d unique remain", merged, len(kept))
    return kept, merged


def process(tenders: list[dict], new_only: bool | None = None) -> tuple[list[dict], dict]:
    """Full Agent 2 pipeline: filter -> score -> deduplicate."""
    raw_count = len(tenders)
    kept, rejected = apply_filters(tenders, new_only=new_only)
    kept = score_tenders(kept)
    kept, merged = deduplicate(kept)

    stats = {
        "raw": raw_count,
        "after_filters": len(kept) + merged,
        "duplicates_merged": merged,
        "final": len(kept),
        "rejected": rejected,
        "national_only": sum(1 for t in kept if t.get("national_only")),
        "arabic": sum(1 for t in kept if t.get("language") == "ar"),
    }
    return kept, stats
