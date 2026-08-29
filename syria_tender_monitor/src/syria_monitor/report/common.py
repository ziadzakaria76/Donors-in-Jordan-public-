"""Shared report vocabulary."""

from __future__ import annotations

from datetime import date
from typing import Optional

from ..models import Tender
from ..screening import DISCLAIMER

SCREENING_DISCLAIMER = DISCLAIMER
LINK_LABELS = {
    "inside_syria": "Inside Syria",
    "cross_border_hub": "Cross-border hub",
    "regional_crisis": "Regional Syria-crisis",
    "refugee_hosting_only": "Refugee-hosting country only",
    "unclassified": "Unclassified",
}


def fmt_date(value: Optional[date]) -> str:
    return value.strftime("%d-%b-%Y") if value else "not published"


def fmt_value(tender: Tender) -> str:
    if tender.estimated_value_usd:
        return f"US$ {tender.estimated_value_usd:,.0f}"
    if tender.raw_value:
        currency = tender.raw_currency or ""
        return f"{currency} {tender.raw_value}".strip() + " (as published, not converted)"
    return "not published"


def badges(tender: Tender) -> list[str]:
    out = []
    if tender.is_new:
        out.append("NEW")
    if tender.is_pipeline:
        out.append("PIPELINE - not yet biddable")
    if tender.eligibility:
        out.append(f"ELIGIBILITY: {tender.eligibility[:80]}")
    if tender.closing_date is None:
        out.append("DEADLINE NOT PUBLISHED - verify")
    if tender.language == "ar":
        out.append("AR")
    if tender.screening:
        out.append("SANCTIONS FLAG - triage only")
    for flag in tender.value_flags:
        if flag.startswith("syp_") or flag.startswith("value_implausible"):
            out.append(flag.replace("_", " "))
    return out


def split_live_pipeline(tenders: list[Tender]) -> tuple[list[Tender], list[Tender]]:
    live = [t for t in tenders if not t.is_pipeline]
    pipeline = [t for t in tenders if t.is_pipeline]
    return live, pipeline
