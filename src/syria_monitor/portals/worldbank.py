"""World Bank procurement notices.

The API's country parameter is silently ignored. `countryshortname=` returns
HTTP 200 and worldwide notices -- Pakistan, Laos, Bolivia, the Caribbean -- with
no error and no warning, and a response that looks entirely normal. So it is
not sent at all here; the shared gate does the country check over the response.

Note the same name behaves differently in each role: as a REQUEST parameter
countryshortname is ignored, as a RESPONSE field it is one of the names the
country actually arrives under. Read it, do not send it.

The Bank writes the country as "Syrian Arab Republic", not "Syria", wherever it
appears -- which is why the matcher enumerates that spelling.
r"""

from __future__ import annotations

import re
from typing import Any

from .base import ApiPortal

ENDPOINT = "https://search.worldbank.org/api/v2/procnotices"

# The response carries several kinds of id. Only an OP-prefixed notice id builds
# a working detail URL; a project id (P175447) or an internal number produces a
# 404. A dead link is worse than no link, because a dead link looks checked.
NOTICE_ID_RE = re.compile(r"^OP\d{6,}$")
DETAIL_URL = "https://projects.worldbank.org/en/projects-operations/procurement-detail/{id}"

COUNTRY_FIELDS = ("project_ctry_name", "countryshortname", "country_name", "countryname",
                  "cty_name", "country", "project_country")


class WorldBankPortal(ApiPortal):
    name = "worldbank"
    label = "World Bank"
    url = ENDPOINT

    def _params(self, offset: int = 0) -> dict:
        terms = self.profile.get("strong_terms", [])
        qterm = terms[0] if terms else ""
        return {
            "format": "json",
            "rows": int(self.cfg.get("page_size", 100)),
            "os": offset,
            # qterm is a FULL-TEXT search: every record it returns contains this
            # word somewhere in its indexed text. That is precisely why the
            # description below is not offered to the text check.
            "qterm": qterm,
        }

    def raw_payload(self) -> Any:
        return self.fetcher.json(ENDPOINT, params=self._params())

    def fetch_tenders(self) -> list[dict]:
        records: list[dict] = []
        offset = 0
        page_size = int(self.cfg.get("page_size", 100))
        max_pages = int(self.cfg.get("max_pages", 5))

        for _ in range(max_pages):
            payload = self.fetcher.json(ENDPOINT, params=self._params(offset))
            notices = payload.get("procnotices") or payload.get("notices") or []
            if isinstance(notices, dict):
                notices = list(notices.values())
            if not notices:
                break
            for notice in notices:
                records.append(self._to_record(notice))
            if len(notices) < page_size:
                break
            offset += page_size
        return records

    def _to_record(self, notice: dict) -> dict:
        notice_id = str(notice.get("id") or notice.get("notice_id") or "").strip()
        record = {
            "id": notice_id or notice.get("bid_reference_no"),
            "title": notice.get("notice_title") or notice.get("project_name") or "",
            "url": self.build_link(notice_id),
            "posted_date": notice.get("submission_date") or notice.get("noticedate")
                           or notice.get("publication_date"),
            "closing_date": notice.get("submission_deadline_date") or notice.get("bid_deadline_date")
                            or notice.get("deadline"),
            "notice_type": notice.get("procurement_method") or notice.get("notice_type")
                           or notice.get("noticetype"),
            "sector": notice.get("project_sector") or notice.get("sector"),
            "description": notice.get("notice_text") or notice.get("description"),
            "contact": notice.get("contact_email") or notice.get("contact"),
            "value_text": notice.get("contract_value") or notice.get("estimated_cost"),
            # Only the title is safe to text-match. notice_text is the indexed
            # body the API already matched on: re-reading it here would be a
            # second layer looking at the exact field the first one matched, so
            # it could never reject anything. In a previous build that kept
            # 500 of 500 and put water-supply consultancies in Blantyre, Malawi
            # into the report as opportunities in the target country.
            "_safe_text_fields": ["title", "project_name"],
            "project_name": notice.get("project_name"),
        }
        for field in COUNTRY_FIELDS:
            if notice.get(field):
                record[field] = notice[field]
        return record

    @staticmethod
    def build_link(notice_id: str) -> str | None:
        """Build the detail URL only from a genuine notice id."""
        if notice_id and NOTICE_ID_RE.match(notice_id.strip()):
            return DETAIL_URL.format(id=notice_id.strip())
        return None
