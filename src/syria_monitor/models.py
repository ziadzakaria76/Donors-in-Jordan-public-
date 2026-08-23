"""The standard tender record every portal module must return."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Optional


# syria_link_type values. These are NOT collapsed into a boolean: the report
# counts all four every run so an excluded category is visible and auditable.
INSIDE = "inside_syria"
CROSS_BORDER = "cross_border_hub"
REGIONAL = "regional_crisis"
REFUGEE_HOSTING = "refugee_hosting_only"
UNCLASSIFIED = "unclassified"

LINK_TYPES = (INSIDE, CROSS_BORDER, REGIONAL, REFUGEE_HOSTING, UNCLASSIFIED)


@dataclass
class Tender:
    """One procurement notice, normalised across every portal."""

    id: str
    title: str
    portal: str
    url: Optional[str] = None
    posted_date: Optional[date] = None
    closing_date: Optional[date] = None
    estimated_value_usd: Optional[float] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    eligibility: Optional[str] = None
    contact: Optional[str] = None
    notice_type: Optional[str] = None
    language: Optional[str] = None
    delivery_country: Optional[str] = None
    syria_link_type: str = UNCLASSIFIED

    # --- provenance / diagnostics, not part of the required record ---
    raw_value: Optional[str] = None          # value exactly as published
    raw_currency: Optional[str] = None
    value_flags: list[str] = field(default_factory=list)
    country_fields: dict[str, Any] = field(default_factory=dict)
    match_evidence: list[str] = field(default_factory=list)
    screening: list[dict] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    score: float = 0.0
    is_new: bool = False

    def add_flag(self, flag: str) -> None:
        if flag not in self.flags:
            self.flags.append(flag)

    @property
    def is_pipeline(self) -> bool:
        """GPNs and advance notices: real intelligence, not yet biddable."""
        nt = (self.notice_type or "").lower()
        return "gpn" in nt or "general procurement" in nt or "advance" in nt

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("posted_date", "closing_date"):
            if d[k] is not None:
                d[k] = d[k].isoformat()
        return d
