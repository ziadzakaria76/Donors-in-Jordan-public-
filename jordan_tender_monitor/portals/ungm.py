"""
UNGM -- the United Nations Global Marketplace.

Single richest source for Jordan: UNDP, UNICEF, WFP, UNOPS, UNHCR, UNRWA,
UN Women, FAO and the rest of the UN system.

The public notice board is JavaScript-driven, but its own UI calls a POST search
endpoint returning HTML rows. Order of attack:

  1. the POST search endpoint (fastest, and what the UI itself uses)
  2. Playwright rendering of the public board
  3. static HTML through the standard extraction cascade

Any of the three feeds the same row parser, so a change to one does not lose the
portal.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import config

from . import htmlkit
from .base import (
    PortalError,
    clean_text,
    detect_language,
    http_post,
    make_record,
    mentions_jordan,
)
from .harvester import Source

log = logging.getLogger(__name__)

PORTAL_KEY = "ungm"
LABEL = "UNGM"

BASE = "https://www.ungm.org"
SEARCH_ENDPOINT = f"{BASE}/Public/Notice/Search"
PUBLIC_PAGE = f"{BASE}/Public/Notice"
PAGE_SIZE = 100
MAX_PAGES = 5

SELECTORS = [
    "div.tableRow.dataRow", "div.tableRow", "tr.tableRow",
    "div.resultRow", "table tbody tr", "div[class*='tableRow']",
]
HREF_PATTERN = r"/Public/Notice/\d+"

# This module drives its own fetching (the POST search endpoint first), but
# `run.py --capture ungm` still needs to know which page to pull down to check
# the selectors above against real markup.
SOURCES = [Source(PUBLIC_PAGE, js=True)]

UN_AGENCIES = (
    "UNDP", "UNICEF", "WFP", "UNOPS", "UNHCR", "UNRWA", "UN Women", "FAO",
    "WHO", "IOM", "UNESCO", "UNFPA", "UNIDO", "UNEP", "ILO", "UNODC", "UNV",
)


def _search_payload(page: int) -> dict:
    """Payload mirroring the UNGM notice-board UI's own search request."""
    return {
        "PageIndex": page,
        "PageSize": PAGE_SIZE,
        "Title": "",
        "Description": "",
        "Reference": "",
        "PublishedFrom": "",
        "PublishedTo": "",
        "DeadlineFrom": "",
        "DeadlineTo": "",
        "Countries": [],
        "Agencies": [],
        "NoticeTypes": [],
        "UNSPSCs": [],
        "SortField": "DatePublished",
        "SortAscending": False,
        "isPicker": False,
        "NoticeDisplayType": None,
        "Keyword": "Jordan",
    }


def _rows_from_html(html: str) -> list[dict]:
    return htmlkit.extract_rows(
        html, BASE, selectors=SELECTORS, href_pattern=HREF_PATTERN
    )


def _from_search_endpoint(errors: list[str]) -> list[dict]:
    rows: list[dict] = []
    for page in range(MAX_PAGES):
        try:
            resp = http_post(
                SEARCH_ENDPOINT,
                json=_search_payload(page),
                headers={
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": PUBLIC_PAGE,
                },
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"search endpoint: {exc}")
            break
        if resp.status_code != 200:
            errors.append(f"search endpoint HTTP {resp.status_code}")
            break

        body = resp.text
        try:  # some deployments wrap the fragment in JSON
            payload = resp.json()
            if isinstance(payload, dict):
                body = payload.get("html") or payload.get("Html") or body
        except ValueError:
            pass

        page_rows = _rows_from_html(body)
        if not page_rows:
            break
        rows.extend(page_rows)
        if len(page_rows) < PAGE_SIZE:
            break
    return rows


def _agency_from(text: str) -> str | None:
    lowered = text.lower()
    for agency in UN_AGENCIES:
        if agency.lower() in lowered:
            return agency
    return None


def fetch_tenders() -> list[dict]:
    errors: list[str] = []
    last_html = ""

    collected = _from_search_endpoint(errors)

    if not collected:
        html = htmlkit.render_js(PUBLIC_PAGE, wait_selector="div.tableRow")
        if not html:
            try:
                html = htmlkit.fetch_html(PUBLIC_PAGE)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"public page: {exc}")
                html = ""
        last_html = html or ""
        if html:
            collected = _rows_from_html(html)

    if not collected:
        reason = htmlkit.diagnose(last_html) if last_html else None
        raise PortalError(
            f"{LABEL}: {reason or 'notice board could not be parsed by any extraction layer'}. "
            + (f"Transport errors: {'; '.join(errors[:3])}. " if errors else "")
            + f"Check manually: {PUBLIC_PAGE}"
        )

    if config.ENRICH_FROM_DETAIL:
        budget = [config.DETAIL_FETCH_BUDGET]
        for row in collected:
            if budget[0] <= 0:
                break
            if mentions_jordan(row.get("title", ""), row.get("text", "")):
                htmlkit.enrich_from_detail(row, budget)

    tenders: list[dict] = []
    seen: set[str] = set()
    for row in collected:
        text = row.get("text") or row["title"]
        if not mentions_jordan(row["title"], text):
            continue
        url = row.get("url") or PUBLIC_PAGE
        if url in seen:
            continue
        seen.add(url)
        posted, closing = htmlkit.resolve_dates(row)
        agency = _agency_from(text)
        tenders.append(
            make_record(
                portal_key=PORTAL_KEY,
                title=row["title"],
                url=urljoin(BASE, url),
                posted_date=posted,
                closing_date=closing,
                estimated_value=(row.get("fields") or {}).get("estimated_value") or text,
                description=clean_text(text)[:1500],
                contact=agency,
                notice_type=f"{agency} notice" if agency else "UN procurement notice",
                language=detect_language(row["title"], text),
            )
        )

    log.info("UNGM: %d Jordan notices retrieved", len(tenders))
    return tenders
