"""
EU TED (Tenders Electronic Daily) -- REST API, Tier 1.

TED covers EU-funded external action, which includes Jordan under the
Neighbourhood instrument. The v3 search API takes an expert query string.

VERIFICATION STATUS: never run against the live API. The v3 endpoint replaced
v2 and the query grammar changed with it, so if this portal reports an HTTP 400
the query below is the first thing to check.
"""

from __future__ import annotations

from . import base

API = "https://api.ted.europa.eu/v3/notices/search"
KEY = "ted"

# TED's expert query language. JO is the ISO country code for Jordan; the
# free-text clause catches notices that name Jordan without coding it.
QUERY = '(place-of-performance IN (JO)) OR (FT~"Jordan")'


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


def fetch_tenders() -> list[dict]:
    payload = {
        "query": QUERY,
        "fields": [
            "publication-number", "notice-title", "publication-date",
            "deadline-receipt-tender-date-lot", "notice-type",
            "total-value", "buyer-name", "links", "description-lot",
            "place-of-performance-country-lot",
        ],
        "limit": 250,
        "page": 1,
        "scope": "ACTIVE",
    }
    data = base.post_json(API, payload)

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

    records = []
    for item in items:
        if not isinstance(item, dict):
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

        records.append(base.build_record(
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
        ))

    # TED is EU-wide, so the country filter has to survive the query being
    # loose. Word-boundary matching keeps Jordanstown out.
    return base.jordan_only(records)
