"""
UK Find a Tender -- OCDS API, Tier 1.

This is the portal where country matching matters most. Find a Tender publishes
the entire UK procurement corpus with no country filter available, so every
release has to be matched for Jordan afterwards -- and a substring match on
"jordan" returns Jordanstown in County Antrim, while "amman" returns Ammanford
in Carmarthenshire. utils.text.mentions_jordan uses word boundaries for exactly
this reason.

Pagination is cursor-based: each package carries a links.next URL.

VERIFICATION STATUS: never run against the live API.
"""

from __future__ import annotations

from datetime import date, timedelta

from .. import config, portal_config
from . import base

KEY = "fcdo"
# From portals.json -- see the note in worldbank.py.
API = portal_config.primary_url(KEY)

# The fields portals.json therefore must not set: this portal is a REST
# API and has no HtmlSpec at all, so a selector in the file would be read,
# accepted and then used by nothing. The loader rejects the entry instead,
# and a test keeps this list and the file's `code_owned` in step.
CODE_OWNED = ("selectors", "field_selectors", "anchor_hint", "currency",
              "filter_to_jordan")


def _party_name(parties, role: str) -> str | None:
    if not isinstance(parties, list):
        return None
    for party in parties:
        if isinstance(party, dict) and role in (party.get("roles") or []):
            return party.get("name")
    return None


def fetch_tenders() -> list[dict]:
    base.require_url(API, KEY)
    params = {
        "updatedFrom": (date.today() - timedelta(days=180)).strftime("%Y-%m-%dT00:00:00"),
        "limit": 100,
    }

    records: list[dict] = []
    url = API
    seen_urls: set[str] = set()

    for _ in range(config.MAX_PAGINATION_PAGES):
        if url in seen_urls:
            break
        seen_urls.add(url)

        data = base.fetch_json(url, params=params if url == API else None)
        if not isinstance(data, dict):
            raise base.PortalError("unexpected OCDS response shape", url)

        for release in data.get("releases") or []:
            if not isinstance(release, dict):
                continue
            tender = release.get("tender") or {}
            title = tender.get("title") or release.get("title") or ""
            if not title:
                continue

            value = tender.get("value") or {}
            value_text = None
            if isinstance(value, dict) and value.get("amount") is not None:
                value_text = f"{value.get('currency') or 'GBP'} {value['amount']}"

            period = tender.get("tenderPeriod") or {}
            records.append(base.build_record(
                portal=KEY,
                title=title,
                url=_release_url(release),
                posted=release.get("date"),
                closing=period.get("endDate") if isinstance(period, dict) else None,
                value_text=value_text,
                description=tender.get("description"),
                notice_type=(tender.get("mainProcurementCategory")
                             or release.get("tag", [None])[0] if release.get("tag")
                             else tender.get("mainProcurementCategory")),
                contact=_party_name(release.get("parties"), "buyer")
                        or (release.get("buyer") or {}).get("name"),
                reference=release.get("ocid") or tender.get("id"),
                default_currency=(value.get("currency") if isinstance(value, dict) else None) or "GBP",
            ))

        links = data.get("links") or {}
        next_url = links.get("next") if isinstance(links, dict) else None
        if not next_url:
            break
        url = next_url
        params = None

    # The whole-UK corpus filtered down to Jordan. Word boundaries, not
    # substrings -- see the module docstring.
    return base.jordan_only(records)


def _release_url(release: dict) -> str | None:
    for doc in release.get("tender", {}).get("documents") or []:
        if isinstance(doc, dict) and doc.get("url"):
            return doc["url"]
    ocid = release.get("ocid")
    if ocid:
        return f"https://www.find-tender.service.gov.uk/Notice/{ocid}"
    return None
