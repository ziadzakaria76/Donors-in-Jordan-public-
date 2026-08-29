"""SAM.gov contract opportunities, v2.

Three API facts that cost a day each:
  * ncode is the two-letter PLACE-OF-PERFORMANCE country, so the profile's iso2.
  * postedFrom and postedTo are mandatory, in MM/DD/YYYY.
  * the API rejects any range longer than a year.

That last one is an API constraint, not a lookback policy: a rolling 364-day
window is sent on every run regardless of what the lookback setting says.

No agency filter is applied. USAID formally shut down on 1 July 2025 and the
State Department absorbed its remaining programming, so filtering on State
alone would miss Syria awards published before mid-2025 under USAID -- and
filtering on both adds nothing that ncode plus the shared country gate does not
already do.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

from .base import ApiPortal

ENDPOINT = "https://api.sam.gov/prod/opportunities/v2/search"
MAX_RANGE_DAYS = 364          # API rejects > 1 year


class SamGovPortal(ApiPortal):
    name = "samgov"
    label = "SAM.gov"
    url = ENDPOINT
    requires_key = "SAM_API_KEY"

    def unavailable_reason(self):
        if not os.environ.get(self.requires_key):
            return (f"{self.requires_key} not set -- free key from sam.gov, "
                    "approval takes 1-4 weeks; portal stays disabled until then")
        return None

    def _params(self, offset: int = 0) -> dict:
        today = date.today()
        start = today - timedelta(days=MAX_RANGE_DAYS)
        return {
            "api_key": os.environ.get(self.requires_key, ""),
            "limit": int(self.cfg.get("page_size", 100)),
            "offset": offset,
            "postedFrom": start.strftime("%m/%d/%Y"),
            "postedTo": today.strftime("%m/%d/%Y"),
            "ncode": self.profile.get("iso2", ""),
        }

    def raw_payload(self) -> Any:
        return self.fetcher.json(ENDPOINT, params=self._params())

    def fetch_tenders(self) -> list[dict]:
        records: list[dict] = []
        page_size = int(self.cfg.get("page_size", 100))
        offset = 0
        for _ in range(int(self.cfg.get("max_pages", 5))):
            payload = self.fetcher.json(ENDPOINT, params=self._params(offset))
            rows = payload.get("opportunitiesData") or []
            if not rows:
                break
            records.extend(self._to_record(r) for r in rows)
            if len(rows) < page_size:
                break
            offset += page_size
        return records

    def _to_record(self, row: dict) -> dict:
        place = row.get("placeOfPerformance") or {}
        country = (place.get("country") or {}) if isinstance(place, dict) else {}
        record = {
            "id": row.get("noticeId"),
            "title": row.get("title") or "",
            "url": row.get("uiLink"),
            "posted_date": row.get("postedDate"),
            "closing_date": row.get("responseDeadLine"),
            "notice_type": row.get("type") or row.get("baseType"),
            "description": row.get("description"),
            "contact": _first_contact(row),
            "eligibility": row.get("typeOfSetAsideDescription"),
            "sector": row.get("classificationCode"),
            "_safe_text_fields": ["title"],
        }
        code = country.get("code") if isinstance(country, dict) else None
        if code:
            record["ncode"] = code
        elif isinstance(place, dict) and place.get("city"):
            record["country"] = (place.get("state") or {}).get("name") or place.get("city", {}).get("name")
        return record


def _first_contact(row: dict) -> str | None:
    contacts = row.get("pointOfContact") or []
    if isinstance(contacts, list) and contacts:
        first = contacts[0]
        if isinstance(first, dict):
            return first.get("email") or first.get("fullName")
    return None
