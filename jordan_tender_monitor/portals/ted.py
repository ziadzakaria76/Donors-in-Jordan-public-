"""
EU TED (Tenders Electronic Daily) -- public search API, no key required for reads.

  POST https://api.ted.europa.eu/v3/notices/search

TED has changed its request schema more than once. Two request shapes are tried
in order and the first that returns notices wins:

  1. the shape given in the build spec  ({"q": ..., "filters": {...}})
  2. the currently documented expert-query shape ({"query": "<expert syntax>"})

Results are paginated by incrementing `page`.
"""

from __future__ import annotations

import logging

from .base import PortalError, clean_text, http_post, make_record

log = logging.getLogger(__name__)

PORTAL_KEY = "ted"
ENDPOINT = "https://api.ted.europa.eu/v3/notices/search"
PAGE_SIZE = 100
MAX_PAGES = 10

FIELDS = [
    "publication-number", "notice-title", "title", "description-lot",
    "deadline-receipt-request", "estimated-value", "notice-type",
    "buyer-name", "buyer-country", "publication-date", "links",
    "place-of-performance", "contract-nature", "organisation-country",
]

# Expert-search syntax: notices whose place of performance or buyer country is Jordan
EXPERT_QUERY = (
    '(place-of-performance IN (JOR) OR organisation-country-serv-prov IN (JOR) '
    'OR FT~"Jordan")'
)


def _payload_spec_shape(page: int) -> dict:
    return {
        "q": "Jordan",
        "filters": {"country": ["JO"]},
        "fields": FIELDS,
        "limit": PAGE_SIZE,
        "page": page,
    }


def _payload_expert_shape(page: int) -> dict:
    return {
        "query": EXPERT_QUERY,
        "fields": FIELDS,
        "limit": PAGE_SIZE,
        "page": page,
        "scope": "ALL",
    }


def _extract_rows(payload) -> list[dict]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("notices", "results", "content", "items", "data"):
        block = payload.get(key)
        if isinstance(block, list):
            return [r for r in block if isinstance(r, dict)]
    return []


def _notice_url(row: dict) -> str:
    links = row.get("links")
    if isinstance(links, dict):
        for key in ("html", "pdf", "xml", "self"):
            link = links.get(key)
            if isinstance(link, dict):
                link = link.get("ENG") or link.get("eng") or next(iter(link.values()), "")
            if link:
                return clean_text(link)
    pub = clean_text(row.get("publication-number") or row.get("ND"))
    return f"https://ted.europa.eu/en/notice/-/detail/{pub}" if pub else ""


def _fetch_with(payload_builder) -> list[dict]:
    """Run a paginated search with one request shape. Returns [] if unsupported."""
    rows: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        resp = http_post(
            ENDPOINT,
            json=payload_builder(page),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        if resp.status_code in (400, 404, 422):
            # This request shape is not accepted by the current API version.
            log.debug("TED rejected request shape with HTTP %s", resp.status_code)
            return []
        if resp.status_code != 200:
            raise PortalError(f"TED API returned HTTP {resp.status_code}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise PortalError(f"TED API returned non-JSON content: {exc}") from exc

        page_rows = _extract_rows(payload)
        if not page_rows:
            break
        rows.extend(page_rows)
        if len(page_rows) < PAGE_SIZE:
            break
    return rows


def fetch_tenders() -> list[dict]:
    rows = _fetch_with(_payload_spec_shape)
    if not rows:
        log.info("TED: spec request shape returned nothing, trying expert query")
        rows = _fetch_with(_payload_expert_shape)

    tenders: list[dict] = []
    for row in rows:
        title = clean_text(row.get("notice-title") or row.get("title") or row.get("TI"))
        if not title:
            continue
        description = clean_text(
            row.get("description-lot") or row.get("description") or ""
        )
        buyer = clean_text(row.get("buyer-name") or row.get("organisation-name"))
        country = clean_text(
            row.get("buyer-country") or row.get("organisation-country")
            or row.get("place-of-performance")
        )
        detail = " | ".join(
            b for b in (
                description,
                f"Buyer: {buyer}" if buyer else "",
                f"Country: {country}" if country else "",
                f"Contract nature: {clean_text(row.get('contract-nature'))}"
                if row.get("contract-nature") else "",
            ) if b
        )
        tenders.append(
            make_record(
                portal_key=PORTAL_KEY,
                native_id=clean_text(row.get("publication-number") or row.get("ND")),
                title=title,
                url=_notice_url(row),
                posted_date=row.get("publication-date") or row.get("PD"),
                closing_date=row.get("deadline-receipt-request") or row.get("DT"),
                estimated_value=row.get("estimated-value") or row.get("estimated-value-cur"),
                description=detail,
                contact=buyer or None,
                notice_type=clean_text(row.get("notice-type")),
            )
        )

    log.info("EU TED: %d notices retrieved", len(tenders))
    return tenders
