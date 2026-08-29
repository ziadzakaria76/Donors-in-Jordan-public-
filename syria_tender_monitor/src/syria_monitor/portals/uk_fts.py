"""UK Find a Tender -- OCDS release packages.

updatedFrom is sent as YYYY-MM-DDT00:00:00 with limit=100, and pagination
follows the package's own next-link. A set of already-seen URLs is kept because
the link chain can loop -- without it the run never terminates.

Buyer and supplier names live in parties[] entries selected by their roles, not
at the top level.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .base import ApiPortal

ENDPOINT = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
PAGE_LIMIT = 100


class UkFindATenderPortal(ApiPortal):
    name = "uk_fts"
    label = "UK Find a Tender"
    url = ENDPOINT

    def _params(self) -> dict:
        days = int(self.cfg.get("updated_within_days", 365))
        since = date.today() - timedelta(days=days)
        return {"updatedFrom": since.strftime("%Y-%m-%dT00:00:00"), "limit": PAGE_LIMIT}

    def raw_payload(self) -> Any:
        return self.fetcher.json(ENDPOINT, params=self._params())

    def fetch_tenders(self) -> list[dict]:
        records: list[dict] = []
        seen_urls: set[str] = set()
        payload = self.fetcher.json(ENDPOINT, params=self._params())

        for _ in range(int(self.cfg.get("max_pages", 5))):
            for release in payload.get("releases") or []:
                records.append(self._to_record(release))
            next_url = ((payload.get("links") or {}).get("next"))
            if not next_url or next_url in seen_urls:
                break                       # the chain can loop
            seen_urls.add(next_url)
            payload = self.fetcher.json(next_url)
        return records

    def _to_record(self, release: dict) -> dict:
        tender = release.get("tender") or {}
        parties = release.get("parties") or []
        buyer = _party_with_role(parties, "buyer") or (release.get("buyer") or {})
        delivery = tender.get("deliveryAddresses") or []
        period = tender.get("tenderPeriod") or {}
        value = tender.get("value") or {}

        record = {
            "id": release.get("ocid") or release.get("id"),
            "title": tender.get("title") or "",
            "url": (tender.get("documents") or [{}])[0].get("url") or release.get("url"),
            "posted_date": release.get("date"),
            "closing_date": period.get("endDate"),
            "notice_type": (tender.get("mainProcurementCategory") or "") or release.get("tag"),
            "description": tender.get("description"),
            "contact": (buyer.get("contactPoint") or {}).get("email") if isinstance(buyer, dict) else None,
            "eligibility": tender.get("eligibilityCriteria"),
            "value_text": f"{value.get('currency', '')} {value.get('amount', '')}".strip() or None,
            "buyer_name": buyer.get("name") if isinstance(buyer, dict) else None,
            "_safe_text_fields": ["title"],
        }
        countries = [a.get("countryName") or a.get("country")
                     for a in delivery if isinstance(a, dict)]
        countries = [c for c in countries if c]
        if countries:
            record["delivery_country"] = countries if len(countries) > 1 else countries[0]
        return record


def _party_with_role(parties: list, role: str) -> dict | None:
    for party in parties:
        roles = [r.lower() for r in (party.get("roles") or [])]
        if role in roles:
            return party
    return None
