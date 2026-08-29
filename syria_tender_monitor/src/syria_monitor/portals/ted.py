"""EU TED (Tenders Electronic Daily), API v3.

Country codes are three-letter ISO, so the profile's iso3 is what TED wants.

TED distinguishes place-of-performance-country(-lot) from buyer-country, which
is exactly the inside-Syria vs cross-border-hub question, handed over for free:
place-of-performance is the delivery country, buyer-country is metadata.

Page limit is 100. Asking for 250 is a silent HTTP 400 on every run.
Many fields come back as multilingual maps like {'eng': [...]}, not strings.
r"""

from __future__ import annotations

import re
from typing import Any

from .base import ApiPortal

ENDPOINT = "https://api.ted.europa.eu/v3/notices/search"
PAGE_LIMIT = 100          # 250 is a silent HTTP 400

FIELDS = ["publication-number", "notice-title", "place-of-performance-country-lot",
          "place-of-performance-country", "buyer-country", "buyer-name",
          "deadline-receipt-request", "publication-date", "notice-type",
          "description-lot", "estimated-value-lot", "links"]

# TED titles follow a "Country - Subject - Detail" convention. Parsing the first
# segment is allowed to throw work away, so the rule is strict: a real country
# name, no digits, nothing sentence-length.
TITLE_COUNTRY_RE = re.compile(r"^\s*([^\d\-–—:]{3,28}?)\s*[-–—:]\s")


def flatten(value: Any) -> str:
    """TED multilingual maps -> plain text."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(flatten(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(flatten(v) for v in value)
    return str(value)


class TedPortal(ApiPortal):
    name = "ted"
    label = "EU TED"
    url = ENDPOINT

    def _query(self) -> str:
        terms = self.profile.get("strong_terms", [])
        iso3 = self.profile.get("iso3", "")
        word = terms[0] if terms else iso3
        return f'FT~"{word}" OR buyer-country={iso3}'

    def _body(self, page: int = 1) -> dict:
        return {"query": self._query(), "page": page, "limit": PAGE_LIMIT, "fields": FIELDS}

    def raw_payload(self) -> Any:
        return self.fetcher.post(ENDPOINT, json=self._body()).text

    def fetch_tenders(self) -> list[dict]:
        records: list[dict] = []
        for page in range(1, int(self.cfg.get("max_pages", 5)) + 1):
            response = self.fetcher.post(ENDPOINT, json=self._body(page))
            if not response.ok:
                raise RuntimeError(f"TED HTTP {response.status} (limit must be <= {PAGE_LIMIT})")
            import json as _json
            payload = _json.loads(response.text)
            notices = payload.get("notices") or []
            if not notices:
                break
            records.extend(self._to_record(n) for n in notices)
            if len(notices) < PAGE_LIMIT:
                break
        return records

    def _to_record(self, notice: dict) -> dict:
        title = flatten(notice.get("notice-title"))
        # Delivery country is place-of-performance; buyer-country is metadata.
        pop = (flatten(notice.get("place-of-performance-country-lot"))
               or flatten(notice.get("place-of-performance-country")))
        links = notice.get("links") or {}
        url = None
        if isinstance(links, dict):
            url = flatten(links.get("html") or links.get("pdf")) or None

        record = {
            "id": flatten(notice.get("publication-number")),
            "title": title,
            "url": url,
            "posted_date": flatten(notice.get("publication-date")),
            "closing_date": flatten(notice.get("deadline-receipt-request")),
            "notice_type": flatten(notice.get("notice-type")),
            "description": flatten(notice.get("description-lot")),
            "contact": flatten(notice.get("buyer-name")),
            "value_text": flatten(notice.get("estimated-value-lot")),
            "buyer_country": flatten(notice.get("buyer-country")),
            "_safe_text_fields": ["title"],
        }
        if pop.strip():
            record["place_of_performance_country"] = pop.strip()
        title_country = self.country_from_title(title)
        if title_country and "place_of_performance_country" not in record:
            record["country"] = title_country
        return record

    @staticmethod
    def country_from_title(title: str) -> str | None:
        m = TITLE_COUNTRY_RE.match(title or "")
        if not m:
            return None
        candidate = m.group(1).strip()
        if len(candidate.split()) > 3 or any(ch.isdigit() for ch in candidate):
            return None
        return candidate
