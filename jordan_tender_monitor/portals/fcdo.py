"""
UK FCDO via Find a Tender (find-tender.service.gov.uk).

Find a Tender exposes a public OCDS API, which is far more reliable than
scraping the search page, so that is used first. The service has no country
facet for the place of delivery, so releases are pulled for a recent window and
filtered for Jordan mentions locally. The HTML search page is the fallback.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from . import htmlkit
from .base import (
    PortalError,
    clean_text,
    http_get,
    make_record,
    mentions_jordan,
    utcnow,
)

log = logging.getLogger(__name__)

PORTAL_KEY = "fcdo"
LABEL = "UK FCDO / Find a Tender"

OCDS_ENDPOINT = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
SEARCH_PAGE = "https://www.find-tender.service.gov.uk/Search/Results"
NOTICE_BASE = "https://www.find-tender.service.gov.uk/Notice/"
WINDOW_DAYS = 365
MAX_PAGES = 12


def _text_of(release: dict) -> str:
    tender = release.get("tender") or {}
    buyer = release.get("buyer") or {}
    parts = [
        clean_text(tender.get("title")),
        clean_text(tender.get("description")),
        clean_text(buyer.get("name")),
    ]
    for item in tender.get("items") or []:
        if not isinstance(item, dict):
            continue
        for addr in item.get("deliveryAddresses") or []:
            if isinstance(addr, dict):
                parts.append(clean_text(addr.get("countryName") or addr.get("region")))
        parts.append(clean_text((item.get("classification") or {}).get("description")))
    return " | ".join(p for p in parts if p)


def _value_usd(tender: dict) -> str | None:
    value = tender.get("value") or tender.get("minValue") or {}
    if isinstance(value, dict) and value.get("amount"):
        return f"{value.get('currency', 'GBP')} {value['amount']}"
    return None


def _from_ocds() -> tuple[list[dict], list[str]]:
    releases: list[dict] = []
    errors: list[str] = []
    now = utcnow()
    params = {
        "updatedFrom": (now - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%S"),
        "updatedTo": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "stages": "tender",
        "limit": 100,
    }
    url = OCDS_ENDPOINT
    for _ in range(MAX_PAGES):
        try:
            resp = http_get(url, params=params if url == OCDS_ENDPOINT else None)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"OCDS API: {exc}")
            break
        if resp.status_code != 200:
            errors.append(f"OCDS API HTTP {resp.status_code}")
            break
        try:
            payload = resp.json()
        except ValueError as exc:
            errors.append(f"OCDS API non-JSON: {exc}")
            break

        batch = payload.get("releases") or []
        if not batch:
            break
        releases.extend(r for r in batch if isinstance(r, dict))

        next_link = ((payload.get("links") or {}).get("next")) or ""
        if not next_link:
            break
        url = next_link
    return releases, errors


def _from_html() -> list[dict]:
    html = htmlkit.fetch_html(SEARCH_PAGE, params={"keywords": "Jordan"})
    rows = htmlkit.extract_rows(
        html,
        SEARCH_PAGE,
        selectors=["li.search-result", "div.search-result", "article",
                   "table tbody tr", "div[class*='search-result']"],
        href_pattern=r"/Notice/\d+",
    )
    if not rows:
        reason = htmlkit.diagnose(html)
        raise PortalError(
            f"{LABEL}: {reason or 'search page could not be parsed by any extraction layer'}. "
            f"Check manually: {SEARCH_PAGE}?keywords=Jordan"
        )

    out: list[dict] = []
    for row in rows:
        text = row.get("text") or row["title"]
        if not mentions_jordan(row["title"], text):
            continue
        posted, closing = htmlkit.resolve_dates(row)
        out.append(
            make_record(
                portal_key=PORTAL_KEY,
                title=row["title"],
                url=row.get("url", SEARCH_PAGE),
                posted_date=posted,
                closing_date=closing,
                estimated_value=(row.get("fields") or {}).get("estimated_value") or text,
                description=clean_text(text)[:1500],
                notice_type="UK Find a Tender notice",
            )
        )
    return out


def fetch_tenders() -> list[dict]:
    releases, errors = _from_ocds()

    tenders: list[dict] = []
    for release in releases:
        blob = _text_of(release)
        if not mentions_jordan(blob):
            continue
        tender = release.get("tender") or {}
        title = clean_text(tender.get("title"))
        if not title:
            continue
        buyer = clean_text((release.get("buyer") or {}).get("name"))
        native = clean_text(release.get("ocid") or release.get("id"))
        tenders.append(
            make_record(
                portal_key=PORTAL_KEY,
                native_id=native,
                title=title,
                url=f"{NOTICE_BASE}{clean_text(release.get('id'))}" if release.get("id") else SEARCH_PAGE,
                posted_date=release.get("date") or tender.get("datePublished"),
                closing_date=(tender.get("tenderPeriod") or {}).get("endDate"),
                estimated_value=_value_usd(tender),
                description=clean_text(tender.get("description")) or blob[:1200],
                contact=buyer or None,
                notice_type=clean_text(tender.get("mainProcurementCategory"))
                or "UK Find a Tender notice",
                eligibility=clean_text((tender.get("eligibilityCriteria") or "")),
            )
        )

    if not releases:
        try:
            tenders = _from_html()
        except Exception as exc:  # noqa: BLE001
            raise PortalError(
                f"{LABEL}: OCDS API and search page both failed. "
                + "; ".join(errors + [str(exc)])
                + f" Check manually: {SEARCH_PAGE}?keywords=Jordan"
            ) from exc

    log.info("FCDO/Find a Tender: %d Jordan notices retrieved", len(tenders))
    return tenders
