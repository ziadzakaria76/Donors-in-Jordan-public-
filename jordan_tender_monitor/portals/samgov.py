"""
SAM.gov contract opportunities (covers USAID and other US government buyers).

  GET https://api.sam.gov/prod/opportunities/v2/search
      ?api_key=KEY&keyword=Jordan&limit=100&offset=0&postedFrom=...&postedTo=...

An API key is required. Registration is free but approval can take 1-4 weeks --
see README section 3. Without a key this module raises PortalError with the
registration instructions, and run.py reports the portal as unavailable rather
than failing the run.

Note: the API requires postedFrom/postedTo and rejects ranges wider than one
year, so the "all currently open" lookback is implemented as a rolling
`SEARCH_WINDOW_DAYS` window plus `active=true`.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import config

from .base import PortalError, clean_text, http_get, make_record, utcnow

log = logging.getLogger(__name__)

PORTAL_KEY = "samgov"
ENDPOINT = "https://api.sam.gov/prod/opportunities/v2/search"
PAGE_SIZE = 100
MAX_PAGES = 10
SEARCH_WINDOW_DAYS = 364  # API rejects ranges of a year or more

REGISTRATION_HELP = (
    "SAM.gov API key missing. Register free at https://sam.gov -> create a "
    "login.gov account -> sign in -> Account Details -> Request Public API Key. "
    "Approval typically takes 1-4 weeks. Then set SAM_API_KEY in .env."
)


def _extract_rows(payload) -> list[dict]:
    if isinstance(payload, dict):
        for key in ("opportunitiesData", "opportunities", "data", "results"):
            block = payload.get(key)
            if isinstance(block, list):
                return [r for r in block if isinstance(r, dict)]
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    return []


def _place(row: dict) -> str:
    place = row.get("placeOfPerformance")
    if isinstance(place, dict):
        country = place.get("country")
        country = country.get("name") if isinstance(country, dict) else country
        city = place.get("city")
        city = city.get("name") if isinstance(city, dict) else city
        return clean_text(" ".join(str(p) for p in (city, country) if p))
    return clean_text(place)


def _contact(row: dict) -> str:
    contacts = row.get("pointOfContact")
    if isinstance(contacts, list) and contacts:
        first = contacts[0]
        if isinstance(first, dict):
            return clean_text(
                " ".join(
                    str(first.get(k))
                    for k in ("fullName", "email", "phone")
                    if first.get(k)
                )
            )
    return clean_text(contacts)


def fetch_tenders() -> list[dict]:
    if not config.SAM_API_KEY:
        raise PortalError(REGISTRATION_HELP)

    today = utcnow().date()
    posted_from = today - timedelta(days=SEARCH_WINDOW_DAYS)

    tenders: list[dict] = []
    for page in range(MAX_PAGES):
        params = {
            "api_key": config.SAM_API_KEY,
            "keyword": "Jordan",
            "limit": PAGE_SIZE,
            "offset": page * PAGE_SIZE,
            "postedFrom": posted_from.strftime("%m/%d/%Y"),
            "postedTo": today.strftime("%m/%d/%Y"),
            "active": "true",
        }
        resp = http_get(ENDPOINT, params=params)
        if resp.status_code in (401, 403):
            raise PortalError(
                f"SAM.gov rejected the API key (HTTP {resp.status_code}). "
                "Check SAM_API_KEY in .env is current and approved."
            )
        if resp.status_code == 429:
            raise PortalError(
                "SAM.gov rate limit reached (public keys are capped at 10 "
                "requests/day). Try again tomorrow or request a higher tier."
            )
        if resp.status_code != 200:
            raise PortalError(f"SAM.gov API returned HTTP {resp.status_code}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise PortalError(f"SAM.gov returned non-JSON content: {exc}") from exc

        rows = _extract_rows(payload)
        if not rows:
            break

        for row in rows:
            title = clean_text(row.get("title"))
            if not title:
                continue
            place = _place(row)
            description = clean_text(row.get("description") or row.get("synopsis"))
            detail = " | ".join(
                b for b in (
                    description,
                    f"Place of performance: {place}" if place else "",
                    f"Agency: {clean_text(row.get('fullParentPathName'))}"
                    if row.get("fullParentPathName") else "",
                    f"NAICS: {clean_text(row.get('naicsCode'))}"
                    if row.get("naicsCode") else "",
                ) if b
            )
            tenders.append(
                make_record(
                    portal_key=PORTAL_KEY,
                    native_id=clean_text(row.get("noticeId")),
                    title=title,
                    url=clean_text(row.get("uiLink") or row.get("link")),
                    posted_date=row.get("postedDate"),
                    closing_date=row.get("responseDeadLine") or row.get("archiveDate"),
                    estimated_value=row.get("award", {}).get("amount")
                    if isinstance(row.get("award"), dict) else None,
                    description=detail,
                    contact=_contact(row),
                    notice_type=clean_text(row.get("type") or row.get("baseType")),
                    eligibility=clean_text(row.get("typeOfSetAsideDescription")),
                )
            )

        if len(rows) < PAGE_SIZE:
            break

    log.info("SAM.gov: %d notices retrieved", len(tenders))
    return tenders
