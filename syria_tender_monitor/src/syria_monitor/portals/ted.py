"""EU TED (Tenders Electronic Daily), API v3.

Country codes are three-letter ISO, so the profile's iso3 is what TED wants.

TED distinguishes place-of-performance-country(-lot) from buyer-country, which
is exactly the inside-Syria vs cross-border-hub question, handed over for free:
place-of-performance is the delivery country, buyer-country is metadata.

Page limit is 100. An unsupported name in FIELDS is also HTTP 400 -- on
page 1, so the portal returns nothing at all; see FIELDS.
Many fields come back as multilingual maps like {'eng': [...]}, not strings.
r"""

from __future__ import annotations

import re
from typing import Any

from .base import ApiPortal

ENDPOINT = "https://api.ted.europa.eu/v3/notices/search"
PAGE_LIMIT = 100          # 250 is a silent HTTP 400

# EVERY NAME HERE IS ONE TED HAS ACCEPTED IN PRODUCTION. An unsupported name
# in this list is not a missing column, it is HTTP 400 on page 1 and the whole
# portal reported down -- which is exactly what happened, every run, until the
# run of 2026-08-30 printed TED's own reply:
#
#   Parameter 'fields' contains unsupported value (supported values are: ...)
#
# The four names that are gone were never verified against the API:
#
#   deadline-receipt-request     -> deadline-receipt-tender-date-lot
#   estimated-value-lot          -> total-value
#   place-of-performance-country -> dropped; the -lot form is the one that works
#   buyer-country                -> dropped from the REQUEST only
#
# This list is the sibling Jordan monitor's, which has been answering 200 in
# production. Country still resolves: place-of-performance-country-lot is
# requested, and _country_from_title() reads TED's own "Country - Subject"
# prefix. buyer-country is still READ from any notice that carries it -- absent
# is free, unsupported is fatal, and those are not the same risk.
FIELDS = ["publication-number", "notice-title", "publication-date",
          "deadline-receipt-tender-date-lot", "notice-type",
          "total-value", "buyer-name", "links", "description-lot",
          "place-of-performance-country-lot"]

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



# TED's rejection for a bad `fields` list enumerates every name it DOES accept
# -- some 48 KB of them. That answers "which of ours is wrong" exactly, and the
# 400-character excerpt in the message truncates it long before the answer
# appears. So the comparison is made here instead of being left to the reader,
# who cannot see the part of the reply that settles it.
_SUPPORTED_RE = re.compile(r"supported values are:\s*(.+?)\s*\)", re.S)


def _unsupported_fields_note(body: str) -> str:
    """Name the fields TED rejected, or return "" when that is not the problem."""
    if "fields" not in body:
        return ""
    match = _SUPPORTED_RE.search(body)
    if not match:
        return ""
    supported = {name.strip() for name in match.group(1).split(",") if name.strip()}
    if not supported:
        return ""
    offending = [name for name in FIELDS if name not in supported]
    if not offending:
        # TED rejected `fields` but every name we sent is in its own list. Say
        # so rather than printing an empty accusation: the fault is elsewhere
        # (the parameter's shape, or a list that is not exhaustive), and a
        # confident wrong answer here is the failure this module already has a
        # docstring about.
        return ("Every field this portal requests appears in TED's supported "
                "list, so the rejection is not the field NAMES. ")
    return f"Fields TED does not support: {', '.join(offending)}. "


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

    def _rejection(self, response, page: int) -> str:
        """Report what TED said, not what we assume it meant.

        This used to append "(limit must be <= 100)" to EVERY non-OK response
        -- a 400 from the query, a 401, a 500, a rate limit -- and PAGE_LIMIT
        has been 100 all along, so the explanation was not merely unhelpful, it
        was false. A live run reported

            EU TED: UNAVAILABLE -- RuntimeError: TED HTTP 400
            (limit must be <= 100)

        which sends the reader to a setting that is already correct, and costs
        a whole portal until somebody disbelieves the message. The same shape
        of confident-but-wrong diagnosis is on record in this codebase twice
        over: a 395-byte response filed as proof an endpoint was dead when the
        request body was wrong, and an extraction layer reporting notices it
        had never looked at.

        So: the status, the query that produced it, and TED's own response
        body. The body is where a v3 rejection names the offending field, and
        it was being discarded. Truncated because an error page can be a whole
        HTML document, and redacted because a URL-shaped error can carry an
        API key -- there is none on this endpoint today, and relying on that
        staying true is how one gets into a log.
        """
        from ..fetch import redact
        body = (response.text or "").strip()
        detail = redact(body[:400]) if body else "(empty response body)"
        return (f"TED HTTP {response.status} on page {page}. "
                f"Query sent: {self._query()!r}, limit={PAGE_LIMIT}. "
                + _unsupported_fields_note(body) +
                f"TED said: {detail}")

    def fetch_tenders(self) -> list[dict]:
        records: list[dict] = []
        for page in range(1, int(self.cfg.get("max_pages", 5)) + 1):
            response = self.fetcher.post(ENDPOINT, json=self._body(page))
            if not response.ok:
                raise RuntimeError(self._rejection(response, page))
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
            "closing_date": flatten(notice.get("deadline-receipt-tender-date-lot")
                                    or notice.get("deadline-receipt-request")),
            "notice_type": flatten(notice.get("notice-type")),
            "description": flatten(notice.get("description-lot")),
            "contact": flatten(notice.get("buyer-name")),
            "value_text": flatten(notice.get("total-value")
                                  or notice.get("estimated-value-lot")),
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
