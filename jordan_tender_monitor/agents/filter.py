"""
Filter, score and deduplicate.

Filtering policy comes straight from the interview and is deliberately
permissive -- almost nothing is removed, because every removal here is
invisible in the finished report:

  * all sectors, all notice types, no lookback window  (Q1, Q4, Q5)
  * the $100k floor applies ONLY to published values   (Q3)
  * closed tenders out, undated ones kept and flagged  (Q6)
  * national-only tenders kept, flagged, penalised     (Q9)

Scoring is where the report earns its keep, and it has one subtlety worth
stating. A scoring component whose filter is disabled awards every tender the
same points, so it carries no information at all while still occupying weight
that could have gone to a component that discriminates. Such components are
dropped and the remainder renormalised to 100.
"""

from __future__ import annotations

from datetime import date

from rapidfuzz import fuzz

from .. import config
from ..utils import dates as dateutils
from ..utils import money
from ..utils.text import clean, keyword_hits

# ---------------------------------------------------------------------------
# Scoring weights, resolved once against the active configuration
# ---------------------------------------------------------------------------


def active_weights() -> dict[str, float]:
    """Weights renormalised to 100 across components that still discriminate.

    The sector component is dropped when TARGET_SECTORS is empty, because with
    "all sectors" every tender scores identically on it.

    The keyword component is NOT dropped when MATCH_KEYWORDS is empty. Keyword
    *filtering* is off, but RANKING_LEXICON still varies per tender, so the
    component carries real information -- and without it ranking would collapse
    onto value and deadline alone, putting a large road contract above a
    well-matched governance advisory.
    """
    weights = dict(config.SCORE_WEIGHTS)

    if not config.TARGET_SECTORS:
        weights.pop("sector", None)
    if not config.RANKING_LEXICON and not config.MATCH_KEYWORDS:
        weights.pop("keyword", None)
    if config.MIN_VALUE_USD is None and not config.KEEP_UNKNOWN_VALUE:
        weights.pop("value", None)

    total = sum(weights.values())
    if total <= 0:
        return {"keyword": 100.0}
    return {k: (v / total) * 100.0 for k, v in weights.items()}


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def _passes_value(record: dict) -> tuple[bool, str | None]:
    value = record.get("estimated_value_usd")
    if value is None:
        # Q3: unknown is not the same as small. Most donor notices publish no
        # value at all, so dropping these would remove most of the pipeline.
        return (config.KEEP_UNKNOWN_VALUE, "Value not published")
    if config.MIN_VALUE_USD is not None and value < config.MIN_VALUE_USD:
        return (False, None)
    return (True, None)


def _passes_deadline(record: dict, today: date) -> tuple[bool, str | None]:
    closing = record.get("closing_date")
    if closing is None:
        return (config.KEEP_UNKNOWN_DEADLINE, config.UNKNOWN_DEADLINE_NOTE)
    if config.EXCLUDE_CLOSED and not dateutils.is_open(closing, today):
        return (False, None)
    return (True, None)


def _passes_undated_lookback(record: dict, today: date) -> bool:
    """A stale UNDATED notice is not an opportunity.

    A dated notice leaves the report when it closes. An undated one never does,
    because there is no deadline to expire -- so undated notices accumulate for
    as long as the source has been publishing them. That was invisible while
    the World Bank read was truncated at 500; once it returned its real 1,625
    notices it produced 1,036 reported opportunities from one portal, most of
    them years old, which is not a bid-review pack.

    THREE CASES, and only the first is filtered:

      * undated with a publication date  -> keep while the publication date is
        inside the window
      * dated                            -> untouched, judged on its deadline
        however old the notice is
      * no dates at all                  -> KEPT. There is nothing to judge it
        on, and inventing a verdict would silently delete live tenders.
    """
    if config.UNDATED_LOOKBACK_DAYS is None:
        return True
    if record.get("closing_date") is not None:
        return True
    posted = record.get("posted_date")
    if posted is None:
        return True
    return (today - posted).days <= config.UNDATED_LOOKBACK_DAYS


def _passes_lookback(record: dict, today: date) -> bool:
    if config.LOOKBACK_DAYS is None:
        return True
    posted = record.get("posted_date")
    if posted is None:
        return True  # never drop on a field the portal did not publish
    return (today - posted).days <= config.LOOKBACK_DAYS


def _passes_sector(record: dict) -> bool:
    if not config.TARGET_SECTORS:
        return True
    return record.get("sector") in config.TARGET_SECTORS


def _passes_keywords(record: dict) -> bool:
    if not config.MATCH_KEYWORDS:
        return True
    blob = f"{record.get('title') or ''} {record.get('description') or ''}"
    return bool(keyword_hits(blob, config.MATCH_KEYWORDS))


def _passes_notice_type(record: dict) -> bool:
    if not config.NOTICE_TYPES:
        return True
    given = (record.get("notice_type") or "").lower()
    return any(t.lower() in given for t in config.NOTICE_TYPES)


def _passes_language(record: dict) -> bool:
    if config.LANGUAGE_MODE == "english_only":
        return record.get("language") != "ar"
    return True


def _passes_eligibility(record: dict) -> bool:
    if config.ELIGIBILITY_MODE != "exclude":
        return True
    return not record.get("eligibility")


def apply_filters(records: list[dict], today: date | None = None
                  ) -> tuple[list[dict], dict[str, int]]:
    """Filter records, returning survivors and a count of what was removed.

    The dropped-reason counts exist so the report can say what was filtered
    rather than leaving it invisible.
    """
    today = today or date.today()
    kept: list[dict] = []
    dropped: dict[str, int] = {}

    def drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    for record in records:
        flags = list(record.get("flags") or [])

        ok, flag = _passes_deadline(record, today)
        if not ok:
            drop("closed")
            continue
        if flag:
            flags.append(flag)

        ok, flag = _passes_value(record)
        if not ok:
            drop("below minimum value")
            continue
        if flag:
            flags.append(flag)

        if not _passes_undated_lookback(record, today):
            drop(f"undated and published over {config.UNDATED_LOOKBACK_DAYS} days ago")
            continue
        if not _passes_lookback(record, today):
            drop("outside lookback window")
            continue
        if not _passes_sector(record):
            drop("sector not targeted")
            continue
        if not _passes_keywords(record):
            drop("no keyword match")
            continue
        if not _passes_notice_type(record):
            drop("notice type not targeted")
            continue
        if not _passes_language(record):
            drop("language excluded")
            continue
        if not _passes_eligibility(record):
            drop("eligibility restricted")
            continue

        if record.get("language") == "ar":
            flags.append(config.ARABIC_FLAG_NOTE)
        if record.get("eligibility"):
            flags.append(record["eligibility"])

        record["flags"] = flags
        kept.append(record)

    return kept, dropped


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

_KEYWORD_SATURATION = 5   # hits beyond this add nothing


def _keyword_component(record: dict) -> float:
    blob = f"{record.get('title') or ''} {record.get('description') or ''}"
    lexicon = config.MATCH_KEYWORDS or config.RANKING_LEXICON
    if not lexicon:
        return 0.0

    hits = keyword_hits(blob, lexicon)
    # A title hit says more than a body hit -- donor titles are terse, so a
    # match there is deliberate.
    title_hits = keyword_hits(record.get("title") or "", lexicon)

    # Guard the division: an empty lexicon or zero hits must not raise.
    density = min(len(hits) / _KEYWORD_SATURATION, 1.0) if _KEYWORD_SATURATION else 0.0
    score = 0.7 * density + 0.3 * min(len(title_hits) / 2.0, 1.0)

    penalty = keyword_hits(blob, config.DEPRIORITISE_LEXICON)
    if penalty:
        score *= 0.55

    record["_keyword_hits"] = sorted(set(hits))[:12]
    return max(0.0, min(score, 1.0))


def _sector_component(record: dict) -> float:
    if not config.TARGET_SECTORS:
        return 0.0
    return 1.0 if record.get("sector") in config.TARGET_SECTORS else 0.0


def _value_component(record: dict) -> float:
    value = record.get("estimated_value_usd")
    if value is None:
        # Mid-band: unknown value must neither dominate the ranking nor sink,
        # since most of the pipeline has no published value.
        return config.UNKNOWN_VALUE_SCORE_FRACTION
    floor = config.MIN_VALUE_USD or 100_000.0
    if value <= floor:
        return 0.35
    ceiling = floor * 50
    span = max(ceiling - floor, 1.0)
    return min(0.35 + 0.65 * ((value - floor) / span), 1.0)


def _urgency_component(record: dict, today: date) -> float:
    """Scored as time available to respond, not as nearness of the deadline.

    A tender closing tomorrow is not an opportunity, it is a missed one. What
    matters for a bid pipeline is whether there is enough runway to write a
    credible proposal.
    """
    days = dateutils.days_until(record.get("closing_date"), today)
    if days is None:
        return 0.5     # unknown deadline: neutral, and flagged elsewhere
    if days < 0:
        return 0.0
    if days <= 5:
        return 0.15
    if days <= 12:
        return 0.5
    if days <= 30:
        return 1.0
    if days <= 75:
        return 0.85
    return 0.6


def score(record: dict, today: date | None = None,
          weights: dict[str, float] | None = None) -> float:
    """Score a tender 0-100 under the active, renormalised weights."""
    today = today or date.today()
    weights = weights if weights is not None else active_weights()

    components = {
        "keyword": _keyword_component(record),
        "sector": _sector_component(record),
        "value": _value_component(record),
        "urgency": _urgency_component(record, today),
    }

    total = sum(weights[name] * components[name]
                for name in weights if name in components)

    if record.get("eligibility") and config.ELIGIBILITY_MODE == "flag":
        total -= config.NATIONAL_ONLY_PENALTY

    record["_components"] = {k: round(v, 3) for k, v in components.items()
                            if k in weights}
    return round(max(0.0, min(total, 100.0)), 1)


def score_all(records: list[dict], today: date | None = None) -> list[dict]:
    today = today or date.today()
    weights = active_weights()
    for record in records:
        record["score"] = score(record, today, weights)
    return records


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def deduplicate(records: list[dict]) -> tuple[list[dict], int]:
    """Collapse the same notice appearing on more than one portal.

    A World Bank-financed assignment routinely shows up on the World Bank site
    and on UNGM. The surviving copy keeps the better data and records where
    else it was seen, so nothing is hidden by the merge.

    Fuzzy title matching applies ONLY across portals. Within a single portal,
    two notices must share a URL to be treated as the same thing. Donor portals
    publish numbered lots and near-identical sister assignments -- "Governance
    Advisory Assignment 5" and "Assignment 6" score 97 on token similarity and
    would collapse into one, silently deleting a real tender. Cross-portal
    duplication is what this function exists to fix; same-portal similarity is
    usually a genuinely different contract.
    """
    if not records:
        return [], 0

    ordered = sorted(records, key=lambda r: (-(r.get("score") or 0),
                                             r.get("title") or ""))
    kept: list[dict] = []
    merged = 0

    for record in ordered:
        title = clean(record.get("title")).lower()
        duplicate = None
        for existing in kept:
            if record.get("url") and record["url"] == existing.get("url"):
                duplicate = existing
                break
            if record.get("portal") == existing.get("portal"):
                continue  # same portal: only an identical URL counts
            other = clean(existing.get("title")).lower()
            if not title or not other:
                continue
            if fuzz.token_sort_ratio(title, other) >= config.DEDUPE_SIMILARITY_THRESHOLD:
                duplicate = existing
                break

        if duplicate is None:
            record["also_on"] = []
            kept.append(record)
            continue

        merged += 1
        also = duplicate.setdefault("also_on", [])
        label = config.PORTAL_NAMES.get(record["portal"], record["portal"])
        if label not in also:
            also.append(label)
        # Keep whichever copy actually has the field.
        for field_name in ("closing_date", "posted_date", "estimated_value_usd",
                           "description", "contact", "notice_type", "eligibility"):
            if duplicate.get(field_name) in (None, "") and record.get(field_name):
                duplicate[field_name] = record[field_name]

    return kept, merged


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


def process(records: list[dict], today: date | None = None) -> dict:
    """Filter, score, deduplicate. Returns results plus what was dropped."""
    today = today or date.today()
    kept, dropped = apply_filters(records, today)
    kept = score_all(kept, today)
    kept, merged = deduplicate(kept)
    kept.sort(key=lambda r: (-(r.get("score") or 0),
                             r.get("closing_date") or date.max))
    return {
        "tenders": kept,
        "dropped": dropped,
        "merged_duplicates": merged,
        "weights": active_weights(),
        "scanned": len(records),
    }


def summarise_value(record: dict) -> str:
    return money.format_usd(record.get("estimated_value_usd"))
