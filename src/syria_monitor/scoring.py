"""Ranking.

A scoring component that awards every tender the same points carries no
information: with sector filtering off, a "matches your sectors" component gives
everything full marks and just dilutes the components that do discriminate. So
components are enabled per run based on whether they actually separate this
batch, and the surviving weights are renormalised to 100.

Keyword filtering is off in this build, so the ranking lexicon does that work
instead -- otherwise ranking collapses to value and deadline alone. The lexicon
includes Arabic terms; without them Arabic notices always rank last, which in a
Syria build means most of the local pipeline sinks out of sight.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Optional

from .models import INSIDE, Tender

BASE_WEIGHTS = {"lexicon": 40.0, "deadline": 25.0, "value": 20.0, "link_type": 15.0}


def _compile_lexicon(profile: dict) -> dict[str, list[re.Pattern]]:
    out = {}
    for group, terms in (profile.get("ranking_terms") or {}).items():
        out[group] = [re.compile(r"(?<!\w)" + re.escape(t) + r"(?!\w)", re.IGNORECASE)
                      if not _is_arabic(t) else re.compile(re.escape(t))
                      for t in terms]
    return out


def _is_arabic(text: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in text)


def lexicon_hits(tender: Tender, lexicon: dict) -> list[str]:
    blob = " ".join(filter(None, [tender.title, tender.description, tender.sector]))
    hits = []
    for group, patterns in lexicon.items():
        if any(p.search(blob) for p in patterns):
            hits.append(group)
    return hits


def _deadline_points(tender: Tender, today: date) -> Optional[float]:
    if tender.closing_date is None:
        return None
    days = (tender.closing_date - today).days
    if days < 0:
        return 0.0
    if days <= 7:
        return 0.6           # closing this week: real, but hard to mobilise for
    if days <= 21:
        return 1.0
    if days <= 45:
        return 0.85
    return 0.6


def score_batch(tenders: Iterable[Tender], profile: dict, today: Optional[date] = None) -> list[Tender]:
    tenders = list(tenders)
    if not tenders:
        return tenders
    today = today or date.today()
    lexicon = _compile_lexicon(profile)

    raw: dict[str, dict[int, Optional[float]]] = {k: {} for k in BASE_WEIGHTS}
    values = [t.estimated_value_usd for t in tenders if t.estimated_value_usd]
    max_value = max(values) if values else None

    for idx, tender in enumerate(tenders):
        hits = lexicon_hits(tender, lexicon)
        tender.match_evidence = [f"lexicon:{h}" for h in hits] + tender.match_evidence
        groups = max(1, len(lexicon))
        raw["lexicon"][idx] = min(1.0, len(hits) / min(3, groups)) if hits else 0.0
        raw["deadline"][idx] = _deadline_points(tender, today)
        raw["value"][idx] = (tender.estimated_value_usd / max_value
                             if tender.estimated_value_usd and max_value else None)
        raw["link_type"][idx] = 1.0 if tender.syria_link_type == INSIDE else 0.5

    # Keep only components that discriminate within this batch.
    active = {}
    for name, weight in BASE_WEIGHTS.items():
        present = [v for v in raw[name].values() if v is not None]
        if len(present) >= 2 and len(set(round(v, 4) for v in present)) > 1:
            active[name] = weight
    if not active:
        active = {"lexicon": BASE_WEIGHTS["lexicon"]}

    total = sum(active.values())
    weights = {name: (weight / total) * 100.0 for name, weight in active.items()}

    for idx, tender in enumerate(tenders):
        score = 0.0
        for name, weight in weights.items():
            component = raw[name].get(idx)
            if component is None:
                continue
            score += weight * component
        tender.score = round(score, 1)
        tender.match_evidence.append("weights:" + ",".join(f"{k}={v:.0f}" for k, v in weights.items()))
    return tenders
