"""The contract every source adapter implements.

One rule governs this module: an adapter returns what the source actually said,
or it returns nothing. It never invents a field to make a record look complete.
Missing data stays None and the UI shows it as unknown.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Protocol, Sequence


class SourceTier(int, Enum):
    """Reliability tier from section 6 of the brief."""

    STRUCTURED = 1  # ATS JSON endpoints, RSS, official APIs
    PUBLIC_HTML = 2  # plain career pages, agency listings — polite scraping
    AGGREGATOR = 3  # only where terms permit; otherwise deep-link instead


class AccessMode(str, Enum):
    """How we are permitted to reach a source.

    DEEP_LINK exists because several portals forbid automated access. For those
    we generate a pre-filtered search URL the human opens themselves, which is
    legitimate and robust. An adapter declaring DEEP_LINK must never fetch.
    """

    FETCH = "fetch"
    DEEP_LINK = "deep_link"


@dataclass(frozen=True, slots=True)
class JobPosting:
    """A single posting as the source reported it.

    Deliberately free of scoring, lane or tier fields — those are derived later
    by the scoring engine. Keeping them apart means a re-score never requires a
    re-fetch, and a scoring change can be replayed over history.
    """

    source_id: str
    source_job_id: str
    title: str
    employer: str
    url: str

    description: str | None = None
    location: str | None = None
    posted_date: date | None = None
    closing_date: date | None = None
    salary_raw: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    language: str = "en"
    raw: dict = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        for name in ("source_id", "source_job_id", "title", "employer", "url"):
            if not (getattr(self, name) or "").strip():
                raise ValueError(f"JobPosting.{name} must be non-empty")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError(f"JobPosting.url must be absolute, got {self.url!r}")

    @property
    def fingerprint(self) -> str:
        """Stable identity for deduplication across scans and across sources.

        Keyed on source plus the source's own id — not on the title, which
        portals reword, and not on the URL, which can carry tracking params.
        """
        return hashlib.sha256(
            f"{self.source_id}::{self.source_job_id}".encode()
        ).hexdigest()[:32]

    def searchable(self, fields: Sequence[str]) -> str:
        """Concatenate the named fields for keyword matching."""
        parts = []
        for name in fields:
            value = getattr(self, name, None)
            if value:
                parts.append(str(value))
        return "\n".join(parts)


@dataclass(slots=True)
class FetchResult:
    """What one adapter run produced, including how it failed if it did."""

    source_id: str
    postings: list[JobPosting]
    ok: bool
    error: str | None = None
    fetched_at: datetime | None = None
    http_calls: int = 0

    @classmethod
    def success(cls, source_id: str, postings: list[JobPosting], **kw) -> "FetchResult":
        return cls(source_id=source_id, postings=postings, ok=True, **kw)

    @classmethod
    def failure(cls, source_id: str, error: str, **kw) -> "FetchResult":
        # An empty list, never a fabricated one. A failed scan shows zero and
        # says why; the last known good snapshot is served alongside it.
        return cls(source_id=source_id, postings=[], ok=False, error=error, **kw)


class SourceAdapter(Protocol):
    """Every source is a module implementing exactly this.

    Adding a source must never require touching the scoring engine, and one
    adapter raising must never abort a scan — the runner catches per adapter.
    """

    source_id: str
    display_name: str
    tier: SourceTier
    access_mode: AccessMode
    # Plain-language note for whoever repairs this in six months (section 17):
    # what it fetches, from where, and what shape the response has.
    repair_note: str

    def fetch(self) -> list[JobPosting]:
        """Return current postings. Raise on failure; the runner handles it."""
        ...


class DeepLinkSource:
    """A source we are not permitted to scrape.

    Bayt's terms prohibit any spider, robot or intelligent agent from navigating
    the site, but explicitly permit the saved searches the site itself provides.
    LinkedIn prohibits automated access outright and enforces it. For both, the
    correct build is a one-tap link into the portal's own pre-filtered search.
    """

    access_mode = AccessMode.DEEP_LINK
    tier = SourceTier.AGGREGATOR

    def __init__(
        self,
        source_id: str,
        display_name: str,
        template: str,
        repair_note: str,
        tos_basis: str,
    ) -> None:
        self.source_id = source_id
        self.display_name = display_name
        self.template = template
        self.repair_note = repair_note
        # Why we are not scraping this, quoted from the source's own terms, so
        # the decision is auditable rather than folklore.
        self.tos_basis = tos_basis

    def fetch(self) -> list[JobPosting]:
        raise NotImplementedError(
            f"{self.source_id} is deep-link only: {self.tos_basis}"
        )

    def search_url(self, query: str, location: str = "Saudi Arabia") -> str:
        from urllib.parse import quote_plus

        return self.template.format(
            query=quote_plus(query), location=quote_plus(location)
        )
