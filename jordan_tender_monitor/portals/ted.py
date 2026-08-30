"""
EU TED (Tenders Electronic Daily) -- REST API, Tier 1.

TED covers EU-funded external action, which includes Jordan under the
Neighbourhood instrument. The v3 search API takes an expert query string.

THE PREVIOUS REQUEST WAS REJECTED WITH HTTP 400 ON EVERY LIVE RUN. Two things
in it were wrong against the documented v3 contract:

  * limit was 250. The maximum accepted page size is 100.
  * the country was written "JO". TED's expert search uses three-letter ISO
    codes -- the documented example is buyer-country=DEU -- so Jordan is JOR.

The query is deliberately built from documented constructs only (FT~ and a
three-letter country code). place-of-performance was dropped from the query
because its expert-search spelling could not be confirmed, and an unknown
field name is itself a 400. It is still REQUESTED as a response field, where
being absent costs nothing, and it is what _is_jordan() prefers when present.
"""

from __future__ import annotations

import logging

from .. import portal_config
from ..utils import text as textutil
from . import base

log = logging.getLogger(__name__)

KEY = "ted"
# From portals.json -- see the note in worldbank.py.
API = portal_config.primary_url(KEY)

# The fields portals.json therefore must not set: this portal is a REST
# API and has no HtmlSpec at all, so a selector in the file would be read,
# accepted and then used by nothing. The loader rejects the entry instead,
# and a test keeps this list and the file's `code_owned` in step.
CODE_OWNED = ("selectors", "field_selectors", "anchor_hint", "currency",
              "filter_to_jordan")

# Three-letter ISO, per the documented buyer-country=DEU example.
QUERY = 'FT~"Jordan" OR buyer-country=JOR'

# The documented maximum page size. 250 was a silent 400 on every run.
PAGE_LIMIT = 100


def _text(value) -> str | None:
    """TED returns many fields as {'eng': [...]} multilingual maps."""
    if value in (None, "", [], {}):
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_text(v) or "" for v in value).strip() or None
    if isinstance(value, dict):
        for lang in ("eng", "en", "ENG", "mul"):
            if lang in value:
                return _text(value[lang])
        return _text(next(iter(value.values()), None))
    return str(value)


_COUNTRY_FIELDS = ("place-of-performance-country-lot", "place-of-performance-country",
                   "buyer-country", "country")

# TED writes countries as three-letter ISO codes in these fields.
_JORDAN_CODES = {"jor", "jo"}


import re as _re

# "Austria – License management software development services – Provision ..."
# TED's own convention: the country, an en dash, then the subject. Deliberately
# strict -- a real country name, no digits, nothing long enough to be a
# sentence -- because this rule is allowed to REJECT notices.
_TITLE_COUNTRY_RE = _re.compile(r"^\s*([^\d–—|/]{3,28}?)\s*[–—]\s")


def _country_from_title(title: str | None) -> bool | None:
    """False when TED's own title prefix names a country that is not Jordan.

    Never returns True. A prefix reading "Jordan" is good evidence, but this
    function exists to catch what the full-text query drags in, and admitting
    notices on a title prefix would re-open the same hole from the other side.
    Anything not clearly another country falls through to the text check.
    """
    if not title:
        return None
    match = _TITLE_COUNTRY_RE.match(title)
    if not match:
        return None
    prefix = match.group(1).strip()
    if not prefix or textutil.mentions_jordan(prefix):
        return None
    return False


def _country_value(item: dict) -> str | None:
    """The country the notice ITSELF names, before any verdict is taken on it.

    _country_verdict() has always read these fields and then kept only its
    yes/no. The value is what a reader of the report needs in order to check
    the decision, so it is carried through rather than discarded.
    """
    for name in _COUNTRY_FIELDS:
        value = _text(item.get(name))
        if value:
            return value
    return None


def _country_verdict(item: dict) -> bool | None:
    """True / False from a country FIELD; None when the notice carries none.

    The same trap as the World Bank, and for the same reason: FT~"Jordan" is a
    FULL-TEXT search, so every notice it returns contains the word somewhere,
    and filtering the text afterwards cannot reject any of them. TED is
    EU-wide, so that would mean the whole of European procurement arriving
    labelled as Jordan opportunities.

    Country codes are matched exactly rather than by substring. "JO" must not
    match "JOR" by accident in one direction or "MNG"/"COD" style codes in the
    other, and a country NAME still goes through the word-boundary matcher that
    keeps Jordanstown out.
    """
    for name in _COUNTRY_FIELDS:
        value = _text(item.get(name))
        if not value:
            continue
        codes = {part.strip().lower() for part in value.replace(",", " ").split()}
        if codes & _JORDAN_CODES:
            return True
        return textutil.mentions_jordan(value)

    # No country field came back. TED prefixes a notice title with its country
    # -- "Austria – License management software development services – ..." --
    # and on the first live run that Austrian notice reached the report on a
    # full-text hit alone. The prefix is used ONLY to reject: a leading segment
    # naming some other country is TED saying so itself. A title with no such
    # prefix yields no verdict and still gets the text check.
    return _country_from_title(_text(item.get("notice-title")))


def fetch_tenders() -> list[dict]:
    payload = {
        "query": QUERY,
        "fields": [
            "publication-number", "notice-title", "publication-date",
            "deadline-receipt-tender-date-lot", "notice-type",
            "total-value", "buyer-name", "links", "description-lot",
            "place-of-performance-country-lot",
        ],
        "limit": PAGE_LIMIT,
        "page": 1,
        "scope": "ACTIVE",
    }
    data = base.post_json(base.require_url(API, KEY), payload)

    items = []
    if isinstance(data, dict):
        for key in ("notices", "results", "content", "items"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
    elif isinstance(data, list):
        items = data

    if not items:
        raise base.PortalError(
            "the API responded but returned no notices -- check the v3 expert "
            "query grammar, which changed from v2", API)

    confirmed: list[dict] = []
    unconfirmed: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        # The country FIELD decides where it exists -- see _country_verdict().
        verdict = _country_verdict(item)
        if verdict is False:
            continue

        title = _text(item.get("notice-title") or item.get("title"))
        if not title:
            continue

        number = _text(item.get("publication-number") or item.get("ND"))
        links = item.get("links") or {}
        url = None
        if isinstance(links, dict):
            for key in ("html", "pdf", "xml", "self"):
                candidate = links.get(key)
                url = _text(candidate) if candidate else None
                if url:
                    break
        if not url and number:
            url = f"https://ted.europa.eu/en/notice/-/detail/{number}"

        record = base.build_record(
            portal=KEY,
            title=title,
            url=url,
            posted=_text(item.get("publication-date")),
            closing=_text(item.get("deadline-receipt-tender-date-lot")
                          or item.get("deadline")),
            value_text=_text(item.get("total-value")),
            description=_text(item.get("description-lot") or item.get("description")),
            notice_type=_text(item.get("notice-type")),
            contact=_text(item.get("buyer-name")),
            reference=number,
            default_currency="EUR",
            delivery_country=_country_value(item),
        )
        (confirmed if verdict else unconfirmed).append(record)

    # TED is EU-wide, so a loose query has to be filtered. Text matching is
    # applied only where no country field was returned -- running it over the
    # confirmed ones adds no safety, only false negatives, and running it over
    # everything is exactly the no-op that let Malawi into the World Bank
    # report. Word-boundary matching keeps Jordanstown out.
    kept = confirmed + base.jordan_only(unconfirmed)
    # DOES TED ALREADY CARRY WHAT EIB'S OWN SITE WILL NOT GIVE US?
    #
    # eib.org answers a Cloudflare challenge to every data-centre address,
    # GitHub's runners included -- two probes on 2026-08-30 read 91,699 bytes
    # and found no listing under any of the six layers, and the bank publishes
    # no procurement feed. The EIB portal has therefore never returned a row.
    #
    # But the EIB is an EU institution, so its above-threshold procurement is
    # published on TED, which this module reads successfully. If an
    # EIB-financed Jordan tender reaches TED it is already inside `items`,
    # because the query is FT~"Jordan" OR buyer-country=JOR and such a notice
    # matches on both counts.
    #
    # So the question is answerable from data already fetched, and it is
    # counted rather than argued about. A number above zero means the blocked
    # portal is partly redundant; zero means TED is not a substitute for it and
    # the coverage gap is real. Either way the next run says which, and keeps
    # saying it if TED's coverage changes.
    eib = sum(1 for item in items
              if isinstance(item, dict)
              and "european investment bank" in (_text(item.get("buyer-name")) or "").lower())
    log.info("ted: %d of %d notices name the European Investment Bank as buyer "
             "(eib.org itself is bot-walled and returns nothing)", eib, len(items))

    base.note_scanned(len(items))
    return kept
