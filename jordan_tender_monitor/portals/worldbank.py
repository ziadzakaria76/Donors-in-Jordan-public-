"""
World Bank procurement notices -- REST API, Tier 1.

VERIFIED AGAINST THE LIVE API, TWICE, AND WRONG BOTH TIMES BEFORE THIS.

1. countryshortname=Jordan is IGNORED. The endpoint returned 200 worldwide
   notices -- Pakistan, Laos, Bolivia, the Caribbean -- and because this module
   trusted the parameter and skipped jordan_only(), the first live report led
   with a Caribbean education project.

2. Filtering the TEXT could not fix that, because qterm=Jordan is a full-text
   search and this module stores the searched body as the record description.
   Every notice the API returned therefore contained "Jordan" somewhere, the
   client-side filter kept 500 of 500, and the report carried water-supply
   consultancies in Blantyre, Malawi.

The country FIELD now decides. Text matching is kept only for notices that
carry no country field, where it is the only signal available.

The lesson generalises past this module: defence in depth is not depth when
both layers read the same field.
"""

from __future__ import annotations

from ..utils import text as textutil
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


_COUNTRY_FIELDS = ("project_ctry_name", "countryshortname", "country_name",
                   "countryname", "cty_name", "country", "project_country")


def _country_verdict(item: dict) -> bool | None:
    """True / False from the country FIELD; None when the notice has none.

    The tri-state matters. A notice whose country field says Jordan is Jordan,
    full stop, and must not then be second-guessed by a text match -- "Supply
    of laboratory equipment, Package 3" names neither Jordan nor Amman, and
    text-filtering it away would lose a real tender. A notice with no country
    field at all is genuinely unknown and still needs the text check.

    VERIFIED AGAINST THE LIVE API, and this is a trap worth stating plainly.
    qterm=Jordan is a FULL-TEXT search, so every notice it returns contains the
    word "Jordan" somewhere in its indexed text -- and this module stores
    notice_text, the same body the API searched, as the record description.
    The client-side text filter therefore could not reject anything the API
    returned: it kept 500 of 500, and the report carried water-supply
    consultancies in Blantyre, Malawi as Jordan opportunities.

    Defence in depth is not depth when both layers read the same field. A
    notice mentioning "prior experience in Jordan and Egypt is an advantage" is
    a genuine full-text hit and a genuine non-Jordan tender, and no amount of
    care in the text matcher can tell those apart. The country field can.

    Notices with no country field at all fall through to the text check rather
    than being dropped, because a missing field is not evidence of anything.
    """
    for name in _COUNTRY_FIELDS:
        value = item.get(name)
        if isinstance(value, list):
            value = " ".join(str(v) for v in value)
        if value in (None, "", [], {}):
            continue
        return textutil.mentions_jordan(str(value))
    return None


def fetch_tenders() -> list[dict]:
    params = {
        # Kept even though the API was observed to ignore it: harmless, and it
        # may start working. jordan_only() below is what actually guarantees
        # the result, so nothing depends on this.
        "countryshortname": "Jordan",
        # Free-text narrowing, because without it the response is worldwide and
        # a 200-row page may contain no Jordan notices at all.
        "qterm": "Jordan",
        "format": "json",
        "rows": 500,
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

    # Two buckets: notices the country field CONFIRMS are Jordan, and notices
    # that carry no country field and so still need the text check.
    confirmed: list[dict] = []
    unconfirmed: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        # THE COUNTRY FIELD DECIDES, NOT THE TEXT. See _country_verdict() --
        # reading the country out of free text cannot work here, because the
        # free text is what the API searched.
        verdict = _country_verdict(item)
        if verdict is False:
            continue
        # NOTICE-specific fields first, project name only as a last resort.
        #
        # A World Bank project raises many procurement notices, and they all
        # share one project_name. Reading the title from that field made six
        # different notices appear in the report as six identical lines of
        # "Jordan Education Reform Support Program" -- unreadable, and it
        # inflated the count with what looked like duplicates.
        title = _pick(item, "notice_title", "noticetitle", "bid_description",
                      "bid_desc", "title", default="")
        project = _pick(item, "project_name", "projectname")
        if not title:
            title = project or ""
        elif project and project.lower() not in title.lower():
            # Keep the project as context; it is how these are grouped on the
            # portal and it is genuinely useful when scanning the report.
            title = f"{title} ({project})"
        if not title:
            continue
        url = _pick(item, "url", "notice_url", "pdf_url", "noticeurl")
        record = base.build_record(
            portal=KEY,
            title=title,
            url=url,
            posted=_pick(item, "noticedate", "notice_date", "submission_date",
                         "publication_date", "noticedate_dt"),
            closing=_pick(item, "submission_deadline_date", "bid_closing_date",
                          "deadline", "submissiondeadline", "closing_date"),
            value_text=_pick(item, "contract_value", "estimated_cost",
                             "totalvalue", "amount"),
            description=_pick(item, "notice_text", "description",
                              "bid_description", "project_ctry_name"),
            notice_type=_pick(item, "notice_type", "noticetype", "procurement_type"),
            contact=_pick(item, "contact_email", "contact_name", "agency_name"),
            reference=_pick(item, "id", "notice_no", "bid_reference_no", "project_id"),
            default_currency="USD",
        )
        (confirmed if verdict else unconfirmed).append(record)

    # Defence in depth, applied where it can still tell something apart: the
    # notices with no country field. Running it over the confirmed ones would
    # not add safety, only false negatives -- see _country_verdict().
    kept = confirmed + base.jordan_only(unconfirmed)

    # jordan_only() recorded only the unconfirmed slice. Report the real
    # pre-filter total, so "OK: 12" beside "500 read" stays honest.
    base.note_scanned(len(items))
    return kept
