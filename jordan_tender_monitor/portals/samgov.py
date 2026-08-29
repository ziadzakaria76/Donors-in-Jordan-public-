"""
SAM.gov -- US Government and USAID opportunities. REST API, Tier 1.

Needs a free API key, and approval takes one to four weeks. Until SAM_API_KEY
is set in .env this portal reports itself as unconfigured rather than failed --
the two are different, and conflating them would make a paperwork delay look
like a broken scraper for a month.

VERIFICATION STATUS: never run against the live API (no key, and the host is
blocked from the build environment).
"""

from __future__ import annotations

from datetime import date, timedelta

from .. import config, portal_config
from . import base

KEY = "samgov"
# From portals.json -- see the note in worldbank.py.
API = portal_config.primary_url(KEY)

# The fields portals.json therefore must not set: this portal is a REST
# API and has no HtmlSpec at all, so a selector in the file would be read,
# accepted and then used by nothing. The loader rejects the entry instead,
# and a test keeps this list and the file's `code_owned` in step.
CODE_OWNED = ("selectors", "field_selectors", "anchor_hint", "currency",
              "filter_to_jordan")


def fetch_tenders() -> list[dict]:
    if not config.SAM_API_KEY:
        raise base.PortalError(
            "not configured - no SAM_API_KEY in .env. Request a free key at "
            "sam.gov (approval takes 1-4 weeks), then set SAM_API_KEY.", API)

    # SAM requires an explicit posted-from/to window and rejects ranges over a
    # year. This is a mandatory API parameter, not a lookback filter -- the
    # configured policy is no date cutoff (Q5).
    today = date.today()
    params = {
        "api_key": config.SAM_API_KEY,
        "limit": 500,
        "offset": 0,
        "postedFrom": (today - timedelta(days=364)).strftime("%m/%d/%Y"),
        "postedTo": today.strftime("%m/%d/%Y"),
        "ncode": "JO",           # place-of-performance country
    }

    data = base.fetch_json(base.require_url(API, KEY), params=params)
    items = data.get("opportunitiesData") if isinstance(data, dict) else None
    if items is None and isinstance(data, dict):
        items = data.get("results") or data.get("data") or []
    if not items:
        # A genuinely empty window is normal for Jordan on SAM.gov.
        return []

    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or ""
        if not title:
            continue

        award = item.get("award") or {}
        value_text = None
        if isinstance(award, dict):
            value_text = award.get("amount")

        place = item.get("placeOfPerformance") or {}
        country = ""
        if isinstance(place, dict):
            country = ((place.get("country") or {}).get("name")
                       if isinstance(place.get("country"), dict)
                       else place.get("country")) or ""

        records.append(base.build_record(
            portal=KEY,
            title=title,
            url=item.get("uiLink") or item.get("link"),
            posted=item.get("postedDate"),
            closing=item.get("responseDeadLine") or item.get("responseDeadline"),
            value_text=value_text,
            description=item.get("description") or country,
            notice_type=item.get("type") or item.get("baseType"),
            contact=_contact(item),
            reference=item.get("noticeId") or item.get("solicitationNumber"),
            default_currency="USD",
        ))

    return base.jordan_only(records)


def _contact(item: dict) -> str | None:
    contacts = item.get("pointOfContact")
    if isinstance(contacts, list) and contacts:
        first = contacts[0]
        if isinstance(first, dict):
            return " ".join(
                str(first.get(k)) for k in ("fullName", "email") if first.get(k)
            ) or None
    return None
