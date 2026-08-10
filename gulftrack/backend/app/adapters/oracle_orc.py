"""Oracle Recruiting Cloud (Oracle Fusion "Candidate Experience") adapter.

ROSHN Group's careers portal runs on this platform — its public job search is
served from an Oracle Fusion tenant, which exposes the same
`recruitingCEJobRequisitions` REST resource that every Oracle Recruiting site
uses. That makes it a Tier 1 structured source rather than a scrape.

VERIFICATION STATUS — read before trusting this.

The request shape and the response field names below are taken from Oracle's
published Recruiting Candidate Experience REST resource, not from a recorded
response from ROSHN's tenant, because the environment this was written in
could not reach the host. The parser is tested against a payload built from
that documented shape. Treat the adapter as unverified until it has completed
one successful run against the live tenant and the field mapping has been
checked against what actually came back. `VERIFIED` below is the switch.

Repair note: if this breaks, open the careers site in a browser, open the
network tab, and search for `recruitingCEJobRequisitions`. The request the page
makes is the request this adapter should make. Copy its query string.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from app.adapters.base import AccessMode, JobPosting, SourceTier
from app.adapters.http import PoliteClient

log = logging.getLogger("gulftrack.adapters.oracle")

# Flip to True only after a successful live run with the mapping checked.
VERIFIED = False

PAGE_SIZE = 50
MAX_PAGES = 20  # a guard against a pagination bug walking forever


@dataclass(frozen=True)
class OracleTenant:
    """Where one employer's Oracle Recruiting site lives."""

    source_id: str
    display_name: str
    employer: str
    # e.g. https://fa-epph-saasfaprod1.fa.ocs.oraclecloud.com
    base_url: str
    # The candidate-experience site number, e.g. "CX_1".
    site_number: str


def _first(payload: dict[str, Any], *names: str) -> Any:
    """Oracle spells the same field differently between versions and tenants."""
    for name in names:
        value = payload.get(name)
        if value not in (None, "", []):
            return value
    return None


def parse_date(value: Any) -> date | None:
    """Oracle returns ISO dates, sometimes with a time component.

    Returns None rather than guessing. A wrong closing date is worse than an
    absent one — it would drop a live job off the feed.
    """
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        # fromisoformat covers every shape Oracle has been seen to return:
        # a bare date, a date and time, and a date and time with an offset.
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        log.warning("Unparseable Oracle date %r — leaving it unset", value)
        return None


def _location(requisition: dict[str, Any]) -> str | None:
    primary = _first(requisition, "PrimaryLocation", "Location")
    secondary = requisition.get("secondaryLocations") or []
    names = [
        s.get("Name") for s in secondary
        if isinstance(s, dict) and s.get("Name")
    ]
    parts = [p for p in ([primary] + names) if p]
    return "; ".join(dict.fromkeys(parts)) or None


def parse_requisitions(
    tenant: OracleTenant, payload: dict[str, Any]
) -> list[JobPosting]:
    """Turn one page of the list response into postings.

    Requisitions missing an id or a title are dropped with a log line rather
    than filled in with a placeholder — a job we cannot link back to is
    worthless, and inventing an identifier would corrupt deduplication.
    """
    items = payload.get("items") or []
    if not items:
        return []

    requisitions: list[dict[str, Any]] = []
    for item in items:
        requisitions.extend(item.get("requisitionList") or [])

    postings: list[JobPosting] = []
    for requisition in requisitions:
        req_id = _first(requisition, "Id", "RequisitionId", "RequisitionNumber")
        title = _first(requisition, "Title", "RequisitionTitle")
        if not req_id or not title:
            log.warning(
                "%s: skipping requisition without id or title: %r",
                tenant.source_id, sorted(requisition)[:8],
            )
            continue

        description = _first(
            requisition,
            "ExternalDescriptionStr",
            "ShortDescriptionStr",
            "ExternalQualificationsStr",
            "ShortDescription",
        )

        postings.append(JobPosting(
            source_id=tenant.source_id,
            source_job_id=str(req_id),
            title=str(title).strip(),
            employer=tenant.employer,
            url=job_url(tenant, str(req_id)),
            description=str(description).strip() if description else None,
            location=_location(requisition),
            posted_date=parse_date(_first(requisition, "PostedDate", "PostingStartDate")),
            closing_date=parse_date(_first(requisition, "PostingEndDate", "ExpirationDate")),
            language="en",
            raw=requisition,
        ))
    return postings


def job_url(tenant: OracleTenant, requisition_id: str) -> str:
    return (
        f"{tenant.base_url.rstrip('/')}/hcmUI/CandidateExperience/en/sites/"
        f"{tenant.site_number}/job/{requisition_id}"
    )


def total_count(payload: dict[str, Any]) -> int | None:
    for item in payload.get("items") or []:
        count = item.get("TotalJobsCount")
        if isinstance(count, int):
            return count
    return None


class OracleRecruitingAdapter:
    """Reads one Oracle Recruiting candidate-experience site."""

    tier = SourceTier.STRUCTURED
    access_mode = AccessMode.FETCH

    def __init__(self, tenant: OracleTenant, client: PoliteClient | None = None) -> None:
        self.tenant = tenant
        self.source_id = tenant.source_id
        self.display_name = tenant.display_name
        self._client = client or PoliteClient()
        self.repair_note = (
            f"Reads {tenant.display_name}'s Oracle Recruiting site "
            f"({tenant.base_url}, site {tenant.site_number}) via the "
            f"recruitingCEJobRequisitions REST resource, paging 50 at a time. "
            f"If it breaks: open the careers page in a browser with the network "
            f"tab open, find the recruitingCEJobRequisitions request the page "
            f"itself makes, and copy its query string here. "
            f"{'VERIFIED against the live tenant.' if VERIFIED else 'NOT YET VERIFIED against the live tenant.'}"
        )

    @property
    def _endpoint(self) -> str:
        return (
            f"{self.tenant.base_url.rstrip('/')}"
            f"/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        )

    def _page_params(self, offset: int) -> dict[str, str]:
        # The finder argument is a single positional string, semicolon and
        # comma delimited — this is Oracle's convention, not a mistake.
        finder = (
            f"findReqs;siteNumber={self.tenant.site_number},"
            f"limit={PAGE_SIZE},offset={offset},sortBy=POSTING_DATES_DESC"
        )
        return {
            "onlyData": "true",
            "expand": "requisitionList.secondaryLocations,flexFieldsFacet.values",
            "finder": finder,
        }

    def fetch(self) -> list[JobPosting]:
        collected: list[JobPosting] = []
        seen_ids: set[str] = set()

        for page in range(MAX_PAGES):
            payload = self._client.get_json(
                self._endpoint, params=self._page_params(page * PAGE_SIZE)
            )
            postings = parse_requisitions(self.tenant, payload)
            if not postings:
                break

            fresh = [p for p in postings if p.source_job_id not in seen_ids]
            if not fresh:
                # The tenant ignored our offset and served page one again.
                # Stop rather than loop, and say so — a silent break here would
                # look like a short job list.
                log.warning(
                    "%s: page %s repeated earlier requisitions; stopping",
                    self.source_id, page,
                )
                break

            seen_ids.update(p.source_job_id for p in fresh)
            collected.extend(fresh)

            expected = total_count(payload)
            if len(postings) < PAGE_SIZE:
                break
            if expected is not None and len(collected) >= expected:
                break
        else:
            log.warning(
                "%s: hit the %s page guard; the list may be truncated",
                self.source_id, MAX_PAGES,
            )

        return collected


# --------------------------------------------------------------------------
# Known tenants
# --------------------------------------------------------------------------

# ROSHN's public careers search is served from this Fusion tenant and site.
# Identified from the careers portal's own job-search URL; the tenant host and
# site number still need confirming against a live request.
ROSHN = OracleTenant(
    source_id="roshn-oracle",
    display_name="ROSHN Group careers",
    employer="ROSHN Group",
    base_url="https://fa-epph-saasfaprod1.fa.ocs.oraclecloud.com",
    site_number="CX_1",
)

KNOWN_TENANTS: tuple[OracleTenant, ...] = (ROSHN,)


def oracle_adapters(client: PoliteClient | None = None) -> Iterable[OracleRecruitingAdapter]:
    shared = client or PoliteClient()
    return [OracleRecruitingAdapter(tenant, shared) for tenant in KNOWN_TENANTS]
