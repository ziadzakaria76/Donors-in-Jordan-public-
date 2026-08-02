"""
World Bank procurement notices -- public REST API, no key required.

  GET https://search.worldbank.org/api/v2/procnotices
      ?countryshortname=Jordan&format=json&rows=50&os=0

Paginated with `os` (offset) until a page comes back empty.
"""

from __future__ import annotations

import logging

from .base import PortalError, clean_text, http_get, make_record

log = logging.getLogger(__name__)

PORTAL_KEY = "worldbank"
ENDPOINT = "https://search.worldbank.org/api/v2/procnotices"
ROWS = 50
MAX_PAGES = 40  # 2,000 notices -- far beyond Jordan's realistic volume
NOTICE_BASE = "https://projects.worldbank.org/en/projects-operations/procurement-detail/"


def _extract_rows(payload) -> list[dict]:
    """The API has used several envelope shapes over time; handle them all."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("procnotices", "notices", "documents", "results", "data"):
        block = payload.get(key)
        if isinstance(block, list):
            return [r for r in block if isinstance(r, dict)]
        if isinstance(block, dict):
            # Keyed-by-id mapping, sometimes with bookkeeping keys mixed in
            return [v for k, v in block.items() if isinstance(v, dict) and k != "facets"]
    return []


def _first(row: dict, *keys) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return clean_text(value)
    return ""


def _notice_url(row: dict) -> str:
    url = _first(row, "url", "notice_url", "pdf_url", "noticeurl")
    if url:
        return url if url.startswith("http") else f"https://projects.worldbank.org{url}"
    native = _first(row, "id", "notice_id", "noticeid")
    return f"{NOTICE_BASE}{native}" if native else ""


def fetch_tenders() -> list[dict]:
    tenders: list[dict] = []
    seen_ids: set[str] = set()
    offset = 0

    for _ in range(MAX_PAGES):
        params = {
            "countryshortname": "Jordan",
            "format": "json",
            "rows": ROWS,
            "os": offset,
        }
        resp = http_get(ENDPOINT, params=params)
        if resp.status_code != 200:
            raise PortalError(
                f"World Bank API returned HTTP {resp.status_code}"
            )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise PortalError(f"World Bank API returned non-JSON content: {exc}") from exc

        rows = _extract_rows(payload)
        if not rows:
            break

        for row in rows:
            native = _first(row, "id", "notice_id", "noticeid", "bid_reference_no")
            if native and native in seen_ids:
                continue
            seen_ids.add(native)

            title = _first(
                row, "project_name", "bid_description", "notice_title",
                "noticetitle", "project_ctr_name", "title",
            )
            if not title:
                continue

            description = _first(
                row, "bid_description", "notice_text", "description",
                "project_name", "noticetype_desc",
            )
            procurement_method = _first(row, "procurement_method", "procurement_method_code")
            ref = _first(row, "borrower_contract_ref_no", "bid_reference_no", "contract_ref_no")
            country = _first(row, "project_ctr_name", "countryname", "countryshortname")

            detail_bits = [b for b in (
                f"Country: {country}" if country else "",
                f"Procurement method: {procurement_method}" if procurement_method else "",
                f"Borrower contract ref: {ref}" if ref else "",
                f"Project ID: {_first(row, 'proj_id', 'project_id')}"
                if _first(row, "proj_id", "project_id") else "",
            ) if b]

            tenders.append(
                make_record(
                    portal_key=PORTAL_KEY,
                    native_id=native,
                    title=title,
                    url=_notice_url(row),
                    posted_date=_first(row, "noticedate", "publication_date", "notice_date"),
                    closing_date=_first(row, "submission_date", "bid_closing_date", "deadline"),
                    estimated_value=_first(row, "contract_value", "estimated_cost", "amount"),
                    description=" | ".join([description] + detail_bits) if detail_bits else description,
                    contact=_first(row, "contact", "contact_name", "contact_email", "submission_email"),
                    notice_type=_first(row, "notice_type", "noticetype", "notice_type_desc")
                    or procurement_method,
                    eligibility=_first(row, "eligibility", "bid_eligibility"),
                )
            )

        if len(rows) < ROWS:
            break
        offset += ROWS

    log.info("World Bank: %d notices retrieved", len(tenders))
    return tenders
