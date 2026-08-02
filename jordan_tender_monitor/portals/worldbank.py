"""
World Bank procurement notices -- REST API, Tier 1.

The API takes a country filter directly, so unlike the scraped portals this one
does not need country matching applied afterwards.

VERIFICATION STATUS: the endpoint and its parameters are documented and stable,
but this code has never run against it -- every portal domain is blocked from
the environment it was built in. The field names below are read defensively
(several spellings accepted) precisely because they could not be confirmed.
"""

from __future__ import annotations

from . import base

API = "https://search.worldbank.org/api/v2/procnotices"
KEY = "worldbank"


def _pick(item: dict, *names, default=None):
    """First present, non-empty field among several possible spellings."""
    for name in names:
        value = item.get(name)
        if value not in (None, "", [], {}):
            return value
    return default


def fetch_tenders() -> list[dict]:
    params = {
        "countryshortname": "Jordan",
        "format": "json",
        "rows": 200,
        "os": 0,
    }
    payload = base.fetch_json(API, params=params)

    # The API has used both a flat list and a keyed dict over the years.
    items = []
    if isinstance(payload, dict):
        for key in ("procnotices", "notices", "documents", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                items = value
                break
            if isinstance(value, dict):
                items = [v for v in value.values() if isinstance(v, dict)]
                break
    elif isinstance(payload, list):
        items = payload

    if not items:
        raise base.PortalError(
            "the API responded but contained no notices -- the response shape "
            "may have changed; inspect the JSON by hand", API)

    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _pick(item, "project_name", "projectname", "title", "notice_title",
                      "bid_description", "bid_desc", default="")
        if not title:
            continue
        url = _pick(item, "url", "notice_url", "pdf_url", "noticeurl")
        records.append(base.build_record(
            portal=KEY,
            title=title,
            url=url,
            posted=_pick(item, "noticedate", "notice_date", "submission_date",
                         "publication_date", "noticedate_dt"),
            closing=_pick(item, "submission_deadline_date", "bid_closing_date",
                          "deadline", "submissiondeadline", "closing_date"),
            value_text=_pick(item, "contract_value", "estimated_cost",
                             "totalvalue", "amount"),
            description=_pick(item, "bid_description", "notice_text",
                              "description", "project_ctry_name"),
            notice_type=_pick(item, "notice_type", "noticetype", "procurement_type"),
            contact=_pick(item, "contact_email", "contact_name", "agency_name"),
            reference=_pick(item, "id", "notice_no", "bid_reference_no", "project_id"),
            default_currency="USD",
        ))
    return records
