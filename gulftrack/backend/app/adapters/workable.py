"""Workable job-board adapter.

Qiddiya Investment Company publishes on Workable, board
`qiddiya-investment-company-1`. Their own site sits behind a bot challenge, but
the Workable board answers normally, which makes this a Tier 1 structured
source rather than a scrape.

VERIFICATION STATUS — unlike the Oracle adapter, this one was written from an
observed response, not from documentation. A live call on 10 August 2026
returned HTTP 200, `application/json`, and `{"total": 278, "results": [...]}`
with the field names used below. Two details that only a live call revealed:

  * the endpoint answers to POST, not GET — GET returns "Not Found"
  * the list response carries no job description, so scoring on the list alone
    would miss almost every signal that matters. Descriptions come from a
    per-job call, and a posting whose description cannot be fetched is kept
    without one rather than dropped.

Repair note: if this breaks, open the board in a browser with the network tab
open. The page makes the same POST this adapter makes; copy its body.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from app.adapters.base import AccessMode, JobPosting, SourceTier
from app.adapters.http import FetchFailed, PoliteClient

log = logging.getLogger("gulftrack.adapters.workable")

API_ROOT = "https://apply.workable.com/api/v3/accounts"
BOARD_ROOT = "https://apply.workable.com"

# The board pages ten at a time, so this is a ceiling of roughly 600 postings.
# The first live run set this to 20 and silently stopped at 200 of Qiddiya's
# 278 — the guard fired as designed and logged it, but the ceiling was simply
# too low for a giga-project employer.
MAX_PAGES = 60

# Workable is an API rather than someone's marketing site, so a four-second gap
# between calls is unnecessarily slow for the per-job description fetches.
# One second is still far below anything that could trouble them.
API_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class WorkableBoard:
    source_id: str
    display_name: str
    employer: str
    account: str


def parse_published(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        log.warning("Unparseable Workable date %r — leaving it unset", value)
        return None


def format_location(entry: dict[str, Any]) -> str | None:
    """City, region, country — whichever of them the board actually gave."""
    location = entry.get("location") or {}
    parts = [
        location.get("city"),
        location.get("region"),
        location.get("country"),
    ]
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(str(part))
    if entry.get("remote") and "Remote" not in seen:
        seen.append("Remote")
    return ", ".join(seen) or None


def job_url(board: WorkableBoard, shortcode: str) -> str:
    return f"{BOARD_ROOT}/{board.account}/j/{shortcode}/"


def parse_results(board: WorkableBoard, payload: dict[str, Any]) -> list[JobPosting]:
    """One page of the list response.

    A result without a shortcode is skipped: the shortcode is both the job's
    identity and the only way to build a URL back to it, and inventing either
    would corrupt deduplication or produce a card that links nowhere.
    """
    postings: list[JobPosting] = []
    for entry in payload.get("results") or []:
        shortcode = entry.get("shortcode")
        title = entry.get("title")
        if not shortcode or not title:
            log.warning(
                "%s: skipping a result without shortcode or title (keys: %s)",
                board.source_id, sorted(entry)[:8],
            )
            continue

        # Workable exposes internal-only postings on the same board. They are
        # not open to an external candidate, so they are not matches.
        if entry.get("isInternal"):
            continue
        state = entry.get("state")
        if state and state != "published":
            continue

        departments = entry.get("department") or []
        postings.append(JobPosting(
            source_id=board.source_id,
            source_job_id=str(shortcode),
            title=str(title).strip(),
            employer=board.employer,
            url=job_url(board, str(shortcode)),
            # The list carries no description. Department is the only scope
            # hint available until the per-job call fills this in.
            description="; ".join(str(d) for d in departments) or None,
            location=format_location(entry),
            posted_date=parse_published(entry.get("published")),
            language=str(entry.get("language") or "en"),
            raw=entry,
        ))
    return postings


def strip_html(markup: str) -> str:
    """Crude tag removal.

    Workable returns the description as HTML. The scoring engine matches on
    words, so the tags are noise; a full parser would be a dependency bought
    for nothing.
    """
    import html
    import re

    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", markup, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</(p|div|li|h[1-6])>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t]+", " ", text).strip()


class WorkableAdapter:
    """Reads one Workable board."""

    tier = SourceTier.STRUCTURED
    access_mode = AccessMode.FETCH

    def __init__(
        self,
        board: WorkableBoard,
        client: PoliteClient | None = None,
        *,
        fetch_descriptions: bool = True,
        max_descriptions: int | None = None,
    ) -> None:
        self.board = board
        self.source_id = board.source_id
        self.display_name = board.display_name
        self._client = client or PoliteClient(delay_seconds=API_DELAY_SECONDS)
        self._fetch_descriptions = fetch_descriptions
        # A guard for the first runs. None means every posting, which is what
        # a real scan wants — the description carries most of the signal.
        self._max_descriptions = max_descriptions
        self.repair_note = (
            f"POSTs to {API_ROOT}/{board.account}/jobs and pages with the "
            f"nextPage token. Descriptions come from a GET on "
            f"{API_ROOT}/{board.account}/jobs/<shortcode>. Note the list "
            f"endpoint answers to POST, not GET. If it breaks, open "
            f"{BOARD_ROOT}/{board.account}/ with the browser network tab open "
            f"and copy the request the page itself makes."
        )

    @property
    def _list_url(self) -> str:
        return f"{API_ROOT}/{self.board.account}/jobs"

    def _detail_url(self, shortcode: str) -> str:
        return f"{API_ROOT}/{self.board.account}/jobs/{shortcode}"

    def fetch(self) -> list[JobPosting]:
        postings = self._fetch_list()
        if self._fetch_descriptions:
            postings = self._add_descriptions(postings)
        return postings

    def _fetch_list(self) -> list[JobPosting]:
        collected: list[JobPosting] = []
        seen: set[str] = set()
        token: str | None = None

        for page in range(MAX_PAGES):
            # Exactly the body the API probe saw return HTTP 200. An earlier
            # version added "limit", which the endpoint rejected with a 400 —
            # so the request stays as verified rather than as assumed.
            body: dict[str, Any] = {
                "query": "", "location": [], "department": [],
                "worktype": [], "remote": [],
            }
            if token:
                body["token"] = token

            payload = self._client.post_json(self._list_url, json_body=body)
            batch = parse_results(self.board, payload)
            fresh = [p for p in batch if p.source_job_id not in seen]
            if not fresh:
                break
            seen.update(p.source_job_id for p in fresh)
            collected.extend(fresh)

            token = payload.get("nextPage")
            if not token:
                break
        else:
            log.warning(
                "%s: hit the %s page guard; the list may be truncated",
                self.source_id, MAX_PAGES,
            )

        return collected

    def _add_descriptions(self, postings: list[JobPosting]) -> list[JobPosting]:
        """Fetch each job's description.

        A posting whose description cannot be fetched keeps the department
        summary it already had. Dropping it would hide a real job because of a
        secondary request, and substituting placeholder text would be worse.
        """
        limit = self._max_descriptions
        enriched: list[JobPosting] = []
        failures = 0

        for index, posting in enumerate(postings):
            if limit is not None and index >= limit:
                enriched.extend(postings[index:])
                log.warning(
                    "%s: description fetch capped at %s of %s postings",
                    self.source_id, limit, len(postings),
                )
                break
            try:
                detail = self._client.get_json(self._detail_url(posting.source_job_id))
            except FetchFailed as exc:
                failures += 1
                log.warning(
                    "%s: no description for %s (%s)",
                    self.source_id, posting.source_job_id, exc,
                )
                enriched.append(posting)
                continue

            description = _description_from(detail)
            if not description:
                enriched.append(posting)
                continue

            existing = posting.description
            combined = f"{existing}\n\n{description}" if existing else description
            enriched.append(_with_description(posting, combined))

        if failures:
            log.warning(
                "%s: %s of %s descriptions unavailable",
                self.source_id, failures, len(postings),
            )
        return enriched


def _description_from(detail: dict[str, Any]) -> str | None:
    parts = [
        detail.get("description"),
        detail.get("requirements"),
        detail.get("benefits"),
    ]
    text = "\n\n".join(strip_html(str(p)) for p in parts if p)
    return text.strip() or None


def _with_description(posting: JobPosting, description: str) -> JobPosting:
    """JobPosting is frozen, so replace rather than mutate."""
    from dataclasses import replace

    return replace(posting, description=description)


QIDDIYA = WorkableBoard(
    source_id="qiddiya-workable",
    display_name="Qiddiya Investment Company careers",
    employer="Qiddiya Investment Company",
    account="qiddiya-investment-company-1",
)

KNOWN_BOARDS: tuple[WorkableBoard, ...] = (QIDDIYA,)


def workable_adapters(client: PoliteClient | None = None) -> Iterable[WorkableAdapter]:
    shared = client or PoliteClient(delay_seconds=API_DELAY_SECONDS)
    return [WorkableAdapter(board, shared) for board in KNOWN_BOARDS]
