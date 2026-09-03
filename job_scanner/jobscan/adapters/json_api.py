"""JSON search-API adapters: SuccessFactors, Oracle Recruiting Cloud, Elevatus.

All three return a repeated array of objects, so one walker handles them and
the platform differences live in defaults rather than in code paths. The
defaults matter: they are what makes a discovered endpoint paste-able into
sources.yaml with a two-line block instead of a field-by-field mapping.

A hard rule runs through this module. Where a payload offers only a closing or
application deadline, the posting is built with Posting.from_deadline_only()
and posted_at stays None. A deadline is not a posting date, and treating it as
one makes every ancient vacancy look like it was published this week.

VERIFICATION STATUS: every default below is a documented platform shape, NOT a
confirmed endpoint for any employer in sources.yaml. None has been called --
this environment's egress policy refuses CONNECT to all of them. `api.url`
must be supplied per source from real discovery before an adapter will run.
"""

from __future__ import annotations

from typing import Any, Callable

from ..model import Posting
from ..normalize import dig, parse_date
from . import AdapterError

# Field-name candidates, tried in order, when a source does not map a field
# explicitly. Drawn from each platform's documented response shape.
PLATFORM_DEFAULTS: dict[str, dict[str, Any]] = {
    "successfactors": {
        "records_path": "",
        "fields": {
            "title": ["jobTitle", "title", "jobReqTitle", "externalTitle"],
            "location": ["location", "locationName", "city", "jobLocation"],
            "department": ["department", "businessUnit", "division", "jobFamily"],
            "id": ["jobReqId", "jobId", "id", "requisitionId"],
            "url": ["applyUrl", "jobUrl", "url"],
            "posted_at": ["postedDate", "jobStartDate", "createdDateTime"],
            "closing_at": ["closingDate", "applicationDeadline", "jobEndDate"],
            "employment_type": ["employmentType", "jobType", "scheduleType"],
        },
    },
    "oracle_orc": {
        # Oracle ORC wraps its results exactly this deep. The finder query and
        # siteNumber differ per tenant and must come from discovery.
        "records_path": "items.0.requisitionList",
        "fields": {
            "title": ["Title", "JobTitle"],
            "location": ["PrimaryLocation", "Location", "GeographyNode1"],
            "department": ["Department", "JobFunction", "OrganizationName"],
            "id": ["Id", "RequisitionId", "RequisitionNumber"],
            "url": ["ExternalUrl"],
            "posted_at": ["PostedDate", "PostingStartDate", "CreationDate"],
            "closing_at": ["PostingEndDate", "ClosingDate"],
            "employment_type": ["WorkerType", "JobType", "ScheduleType"],
        },
    },
    "elevatus": {
        "records_path": "data",
        "fields": {
            "title": ["title", "job_title", "name"],
            "location": ["location", "city", "country", "job_location"],
            "department": ["department", "category", "job_category"],
            "id": ["id", "uuid", "slug", "job_id"],
            "url": ["url", "apply_url", "public_url"],
            "posted_at": ["published_at", "created_at", "posted_at"],
            "closing_at": ["expires_at", "deadline", "closing_date"],
            "employment_type": ["type", "employment_type", "job_type"],
        },
    },
}

# The brief flags this explicitly: an unverified default. Every Elevatus tenant
# resolves from its slug alone ONCE this path is confirmed against a live
# tenant -- and not before.
ELEVATUS_DEFAULT_API_PATH = "/api/job-posts"


def _first_present(record: dict[str, Any], candidates: list[str]) -> Any:
    for name in candidates:
        if isinstance(record, dict) and record.get(name) not in (None, ""):
            return record[name]
    return None


def _resolve(record: dict[str, Any], mapping: Any, defaults: list[str]) -> Any:
    """Read one field, preferring an explicit mapping over platform defaults."""
    if isinstance(mapping, str) and mapping:
        return dig(record, mapping)
    return _first_present(record, defaults)


def _describe(payload: Any, limit: int = 12) -> str:
    """A short shape summary, so a bad records_path is diagnosable from the sheet."""
    if isinstance(payload, dict):
        keys = list(payload.keys())[:limit]
        return f"object with keys: {', '.join(map(str, keys))}"
    if isinstance(payload, list):
        head = payload[0] if payload else None
        inner = f"; first item is {_describe(head)}" if head is not None else ""
        return f"array of {len(payload)}{inner}"
    return type(payload).__name__


def _build(
    source: dict[str, Any],
    platform: str,
    records: list[Any],
    spec: dict[str, Any],
    note: Callable[[str], None],
) -> list[Posting]:
    defaults = PLATFORM_DEFAULTS[platform]["fields"]
    mapping = spec.get("fields") or {}
    url_template = spec.get("url_template") or ""
    skipped_untitled = 0
    postings: list[Posting] = []

    for record in records:
        if not isinstance(record, dict):
            skipped_untitled += 1
            continue

        title = _resolve(record, mapping.get("title"), defaults["title"])
        if not title:
            skipped_untitled += 1
            continue

        raw_id = _resolve(record, mapping.get("id"), defaults["id"])
        url = _resolve(record, mapping.get("url"), defaults["url"]) or ""
        if not url and url_template and raw_id is not None:
            url = url_template.format(id=raw_id)

        common = dict(
            source_key=source["key"],
            title=str(title),
            url=str(url),
            location=str(_resolve(record, mapping.get("location"), defaults["location"]) or ""),
            country=source.get("country", ""),
            department=str(_resolve(record, mapping.get("department"), defaults["department"]) or ""),
            employment_type=str(
                _resolve(record, mapping.get("employment_type"), defaults["employment_type"]) or ""
            ),
            raw_id=str(raw_id or ""),
            closing_at=parse_date(
                _resolve(record, mapping.get("closing_at"), defaults["closing_at"])
            ),
        )

        posted = parse_date(_resolve(record, mapping.get("posted_at"), defaults["posted_at"]))
        if posted is None:
            # No posting date in the payload. The deadline, if any, is already
            # carried in closing_at and is NOT promoted to posted_at.
            postings.append(Posting.from_deadline_only(**common))
        else:
            postings.append(Posting(posted_at=posted, **common))

    if skipped_untitled:
        note(
            f"{skipped_untitled} record(s) had no title field and were skipped; "
            "the title mapping may be wrong for this tenant"
        )
    return postings


def _fetch_json(source: dict[str, Any], platform: str, fetcher, note) -> list[Posting]:
    spec = source.get("api") or {}
    url = spec.get("url")
    if not url:
        raise AdapterError(
            f"{source['key']}: no api.url configured. The search endpoint has not been "
            "discovered yet -- run discover_playwright.py against the careers URL and "
            "paste the block it prints. No endpoint is guessed here."
        )

    method = str(spec.get("method", "GET")).upper()
    kwargs: dict[str, Any] = {}
    if spec.get("params"):
        kwargs["params"] = spec["params"]
    if spec.get("headers"):
        kwargs["headers"] = spec["headers"]
    if spec.get("json_body") is not None:
        kwargs["json"] = spec["json_body"]

    response = fetcher.post(url, **kwargs) if method == "POST" else fetcher.get(url, **kwargs)

    if not response.ok:
        detail = response.error
        if response.text:
            detail += f" | body starts: {response.text[:300]}"
        raise AdapterError(f"{source['key']}: {detail}")

    payload = response.json_body
    if payload is None:
        raise AdapterError(
            f"{source['key']}: HTTP {response.status_code} but the body was not JSON "
            f"(content looked like: {response.text[:200]!r}). If this endpoint is "
            "server-rendered, it belongs on the html_table adapter."
        )

    records_path = spec.get("records_path", PLATFORM_DEFAULTS[platform]["records_path"])
    records = dig(payload, records_path)
    if records is None:
        raise AdapterError(
            f"{source['key']}: records_path {records_path!r} does not exist in the "
            f"response ({_describe(payload)})"
        )
    if not isinstance(records, list):
        raise AdapterError(
            f"{source['key']}: records_path {records_path!r} resolved to "
            f"{_describe(records)}, not an array of postings"
        )

    if not records:
        # A genuinely empty board is a real answer, but it is reported as an
        # observation rather than passed off as a clean result.
        note(
            f"endpoint responded HTTP {response.status_code} with a well-formed but "
            f"EMPTY array at {records_path!r} -- zero vacancies, or a filter that "
            "excluded everything"
        )
        return []

    return _build(source, platform, records, spec, note)


def fetch_successfactors(source, fetcher, note) -> list[Posting]:
    return _fetch_json(source, "successfactors", fetcher, note)


def fetch_oracle_orc(source, fetcher, note) -> list[Posting]:
    return _fetch_json(source, "oracle_orc", fetcher, note)


def fetch_elevatus(source, fetcher, note) -> list[Posting]:
    spec = source.get("api") or {}
    if not spec.get("url") and source.get("tenant_slug"):
        note(
            f"built endpoint from tenant slug using the UNVERIFIED default api_path "
            f"{ELEVATUS_DEFAULT_API_PATH!r}; confirm against a live tenant before "
            "trusting this source"
        )
        spec = dict(spec)
        spec["url"] = f"https://{source['tenant_slug']}.elevatus.io{ELEVATUS_DEFAULT_API_PATH}"
        source = dict(source, api=spec)
    return _fetch_json(source, "elevatus", fetcher, note)
