"""The normalized shape every adapter must produce.

One rule is enforced here rather than left to adapter discipline: a closing
or application deadline is never a posting date. Portals routinely expose a
single date field and label it loosely, and mapping it to `posted_at` makes
every ancient vacancy look fresh -- which defeats max_age_days, the profile's
only defence against a stale mirror. So `Posting` takes the two dates through
separate keyword-only arguments and `from_deadline_only()` is the sole
constructor an adapter may use when a payload offers nothing but a deadline.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any


def _clean(value: Any) -> str:
    """Collapse whitespace and strip markup leftovers from scraped text."""
    if value is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Posting:
    source_key: str
    title: str
    url: str = ""
    location: str = ""
    country: str = ""
    department: str = ""
    grade: str = ""
    employment_type: str = ""
    raw_id: str = ""

    # Kept apart on purpose. See the module docstring.
    posted_at: _dt.date | None = None
    closing_at: _dt.date | None = None

    score: int = 0
    score_reasons: list[str] = field(default_factory=list)
    shortlisted: bool = False
    matched_terms: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = _clean(self.title)
        self.location = _clean(self.location)
        self.department = _clean(self.department)
        self.grade = _clean(self.grade)
        self.employment_type = _clean(self.employment_type)
        self.url = (self.url or "").strip()

    @classmethod
    def from_deadline_only(cls, **kwargs: Any) -> "Posting":
        """Build a posting from a payload that exposes only a deadline.

        `posted_at` stays None -- unknown, not inferred. Age filtering then
        treats it as unknown rather than as today, which is the honest
        reading and the one that keeps a stale portal visible as stale.
        """
        if kwargs.pop("posted_at", None) is not None:
            raise ValueError(
                "from_deadline_only() must not be given posted_at; a deadline "
                "is not a posting date"
            )
        return cls(posted_at=None, **kwargs)

    @property
    def identity(self) -> str:
        """Stable key for dedupe across sources and across runs."""
        basis = self.url.strip().lower() or f"{self.source_key}|{self.title.lower()}|{self.location.lower()}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]

    @property
    def age_days(self) -> int | None:
        if self.posted_at is None:
            return None
        return (_dt.date.today() - self.posted_at).days

    def as_row(self) -> dict[str, Any]:
        return {
            "source": self.source_key,
            "title": self.title,
            "grade": self.grade,
            "department": self.department,
            "location": self.location,
            "country": self.country,
            "posted_at": self.posted_at.isoformat() if self.posted_at else "",
            "closing_at": self.closing_at.isoformat() if self.closing_at else "",
            "age_days": "" if self.age_days is None else self.age_days,
            "score": self.score,
            "shortlisted": "yes" if self.shortlisted else "",
            "matched": ", ".join(self.matched_terms),
            "why": "; ".join(self.score_reasons),
            "url": self.url,
        }
