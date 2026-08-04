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

import logging
import re

from ..utils import text as textutil
from . import base

log = logging.getLogger(__name__)

API = "https://search.worldbank.org/api/v2/procnotices"
KEY = "worldbank"

# The public page for a notice. The API returns the identifier; it does not
# return this address, which is why every World Bank row reached the first
# post-pagination report with no link at all.
NOTICE_PAGE = "https://projects.worldbank.org/en/projects-operations/procurement-detail/{id}"

# Notice identifiers look like OP00190487. Matched rather than assumed, because
# the same responses also carry project ids (P175447) and internal numbers, and
# feeding one of those to NOTICE_PAGE builds a link that 404s -- which is worse
# than no link, since a dead link looks checked.
_NOTICE_ID_RE = re.compile(r"^OP\d{6,}$", re.I)


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


_URL_FIELDS = ("url", "notice_url", "noticeurl", "notice_link", "noticelink",
               "bid_url", "pdf_url", "pdfurl", "link", "detail_url",
               "notice_detail_url", "web_url", "weburl")

_ID_FIELDS = ("id", "notice_id", "noticeid", "notice_no", "noticeno",
              "procurement_notice_id", "op_id")


def _notice_url(item: dict) -> str | None:
    """The link for a notice: a URL field if there is one, else built from id.

    EVERY WORLD BANK ROW REACHED THE REPORT WITH NO LINK. Twenty of the
    twenty-seven opportunities in the first clean run were unclickable -- you
    would have had to search the portal by title to act on any of them -- and
    nothing in the run said so, because the record schema allows url=None and
    the renderer simply omits the line. A field this load-bearing failing
    silently is the same class of bug as the 500-row cap: the output looks
    complete because the missing part leaves no hole.

    Two sources, in order:

      1. A URL field, if the response carries one under any of its spellings.
         Preferred whenever present -- it is the API's own answer.
      2. The notice id, rendered into NOTICE_PAGE. The id is what the portal's
         own detail pages are keyed on, so this reconstructs the real address
         rather than inventing a search link.

    Only ids matching _NOTICE_ID_RE are used. A project id would build a
    plausible-looking URL that 404s, and a link that resolves to nothing is
    worse than an absent one: absent is visibly missing, dead reads as checked.
    """
    for name in _URL_FIELDS:
        value = item.get(name)
        if isinstance(value, str) and value.strip().lower().startswith("http"):
            return value.strip()

    for name in _ID_FIELDS:
        value = item.get(name)
        if value in (None, "", [], {}):
            continue
        text = str(value).strip()
        if _NOTICE_ID_RE.match(text):
            return NOTICE_PAGE.format(id=text.upper())
    return None


PAGE_SIZE = 500

# 20 pages of 500 is 10,000 notices, comfortably past the whole qterm=Jordan
# result set. It exists to stop a runaway loop, not to bound the read, and
# reaching it is logged rather than swallowed -- see _fetch_all_items().
MAX_PAGES = 20


def _items_from(payload) -> list:
    """The notice list, whatever shape this response arrived in.

    The API has used both a flat list and a keyed dict over the years.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("procnotices", "notices", "documents", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return [v for v in value.values() if isinstance(v, dict)]
    return []


def _reported_total(payload) -> int | None:
    """What the API says the full result set is, if it says."""
    if not isinstance(payload, dict):
        return None
    for key in ("total", "totalResults", "numFound", "count"):
        value = payload.get(key)
        if value in (None, "", [], {}):
            continue
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            continue
    return None


def _fetch_all_items() -> list:
    """Page through the API instead of reading the first 500 and stopping.

    THE PREVIOUS VERSION ASKED FOR 500 AND GOT EXACTLY 500, which is what a
    truncated read looks like from the outside: the number equals the request,
    so there is no way to tell a complete result from a capped one. Jordan
    notices past the five-hundredth were invisible, and nothing said so.

    Paging stops when a page comes back short, when the API's own total is
    reached, or at MAX_PAGES -- and only the last of those is a cap. Hitting it
    is logged with both numbers, because "read everything" and "read the first
    N and stopped" must never produce the same output.
    """
    items: list = []
    total: int | None = None

    for page in range(MAX_PAGES):
        params = {
            # Kept even though the API was observed to ignore it: harmless, and
            # it may start working. The country field check below is what
            # actually guarantees the result, so nothing depends on this.
            "countryshortname": "Jordan",
            # Free-text narrowing, because without it the response is worldwide
            # and a page may contain no Jordan notices at all.
            "qterm": "Jordan",
            "format": "json",
            "rows": PAGE_SIZE,
            "os": page * PAGE_SIZE,
        }
        payload = base.fetch_json(API, params=params)
        batch = _items_from(payload)
        if total is None:
            total = _reported_total(payload)
        if not batch:
            break

        items.extend(batch)

        # A short page is the end of the data, and it is the ordinary exit.
        if len(batch) < PAGE_SIZE:
            return items
        if total is not None and len(items) >= total:
            return items

    if total is not None and len(items) < total:
        log.warning(
            "worldbank: read %d of %d notices the API reports -- the "
            "%d-page cap was reached and the rest were NOT read",
            len(items), total, MAX_PAGES)
    elif len(items) == MAX_PAGES * PAGE_SIZE:
        log.warning(
            "worldbank: read %d notices and every page was full, so there are "
            "probably more; the %d-page cap was reached",
            len(items), MAX_PAGES)
    return items


def fetch_tenders() -> list[dict]:
    items = _fetch_all_items()

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
        url = _notice_url(item)
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

    # A report row you cannot click through to is barely a lead, and this
    # failed silently for the whole life of the module. Say it out loud.
    unlinked = sum(1 for r in kept if not r.get("url"))
    if unlinked:
        log.warning(
            "worldbank: %d of %d notices have no link -- neither a URL field "
            "nor an id matching %s; run --capture worldbank to see what the "
            "response actually carries",
            unlinked, len(kept), _NOTICE_ID_RE.pattern)

    # jordan_only() recorded only the unconfirmed slice. Report the real
    # pre-filter total, so "OK: 12" beside "500 read" stays honest.
    base.note_scanned(len(items))
    return kept


def capture_api() -> list[tuple[str, list]]:
    """Raw notices for `--capture worldbank`, before any of the picking above.

    The HTML portals could always be inspected this way; the API portals could
    not, and that is precisely how four wrong URL-field guesses survived in
    _pick() unnoticed. Returns the raw items so the diagnostic reports the
    fields the API sends, not the fields this module hoped for.
    """
    return [(API, _fetch_all_items())]
