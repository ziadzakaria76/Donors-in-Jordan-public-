"""
Shared portal plumbing: the record schema, the polite HTTP session, and the
normalisation step that turns an extracted Row into a tender record.

Every portal module exposes exactly one function:

    fetch_tenders() -> list[dict]

and raises PortalError when it cannot deliver. A portal that fails must never
abort the run -- agents/scraper.py catches, diagnoses and reports it as
unavailable with the URL to check by hand.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from datetime import date
from urllib.parse import urlparse

import requests
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)

from .. import config
from ..utils import money, text as textutil
from ..utils.dates import parse_date
from .htmlkit import Row, diagnose, extract

# Standard record. Every portal returns dicts with exactly these keys.
RECORD_FIELDS = (
    "id", "title", "portal", "url", "posted_date", "closing_date",
    "estimated_value_usd", "sector", "description", "eligibility", "contact",
    "notice_type", "language",
)


class PortalError(RuntimeError):
    """A portal could not be read. Carries a diagnosed, actionable reason."""

    def __init__(self, reason: str, url: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.url = url


# ---------------------------------------------------------------------------
# Polite fetching
# ---------------------------------------------------------------------------

_host_lock = threading.Lock()
_last_request: dict[str, float] = {}


def _wait_for_host(url: str) -> None:
    """Hold at least POLITE_DELAY_SECONDS between requests to the same host.

    Per-host rather than global, so thirteen portals still run in parallel
    while no single portal is hammered. Do not lower this to speed runs up --
    the delay is the difference between a monitor and a nuisance, and getting
    the IP blocked costs far more time than it saves.
    """
    host = urlparse(url).netloc
    with _host_lock:
        previous = _last_request.get(host, 0.0)
        gap = time.monotonic() - previous
        if gap < config.POLITE_DELAY_SECONDS:
            time.sleep(config.POLITE_DELAY_SECONDS - gap)
        _last_request[host] = time.monotonic()


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                  "application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9,ar;q=0.6,de;q=0.5",
        "Connection": "keep-alive",
    })
    return session


_SESSION = make_session()


@retry(
    stop=stop_after_attempt(config.MAX_RETRIES),
    wait=wait_exponential(multiplier=config.RETRY_BASE_DELAY, min=2, max=30),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _request(method: str, url: str, **kwargs):
    _wait_for_host(url)
    kwargs.setdefault("timeout", config.REQUEST_TIMEOUT)
    response = _SESSION.request(method, url, **kwargs)
    response.raise_for_status()
    return response


def fetch(url: str, **kwargs) -> str:
    """GET a page as text, or raise PortalError with a diagnosed reason."""
    try:
        response = _request("GET", url, **kwargs)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        if status in (403, 401):
            raise PortalError(
                f"HTTP {status} - blocked (bot wall, egress policy, or the URL "
                f"now requires a login)", url) from exc
        if status == 404:
            raise PortalError("HTTP 404 - the URL has moved; find the current "
                              "listing page", url) from exc
        raise PortalError(f"HTTP {status} from the portal", url) from exc
    except requests.RequestException as exc:
        raise PortalError(
            f"transport error - {type(exc).__name__}: {exc} "
            f"(wrong URL, DNS failure, or the host is blocked)", url) from exc

    response.encoding = response.encoding or response.apparent_encoding
    return response.text


def fetch_json(url: str, **kwargs):
    """GET and parse JSON, or raise PortalError."""
    try:
        response = _request("GET", url, **kwargs)
        return response.json()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        raise PortalError(
            f"HTTP {status} from the API{_error_detail(exc.response)}", url) from exc
    except requests.RequestException as exc:
        raise PortalError(f"transport error - {type(exc).__name__}: {exc}", url) from exc
    except ValueError as exc:
        raise PortalError(f"the API returned something that is not JSON ({exc})",
                          url) from exc


def _error_detail(response, limit: int = 300) -> str:
    """The body of a 4xx, which is where an API says what it disliked.

    TED answered every run with a bare "HTTP 400 from the search endpoint" for
    days. The endpoint had been explaining itself the whole time -- the body
    names the offending parameter -- and the code was discarding it, so the
    only way to make progress was to guess at the query grammar.

    Bounded and stripped of newlines: this goes in a portal status line, and an
    HTML error page must not turn one failure into a wall of markup. Never
    include the request, which for other portals could carry an API key.
    """
    if response is None:
        return ""
    try:
        body = response.text or ""
    except Exception:  # noqa: BLE001 - diagnosing a failure must not fail
        return ""
    body = " ".join(body.split())
    if not body:
        return ""
    return f" - the endpoint said: {body[:limit]}"


def post_json(url: str, payload: dict, **kwargs):
    """POST JSON and parse the response, for search endpoints behind a UI."""
    try:
        response = _request("POST", url, json=payload, **kwargs)
        return response.json()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        raise PortalError(
            f"HTTP {status} from the search endpoint{_error_detail(exc.response)}",
            url) from exc
    except requests.RequestException as exc:
        raise PortalError(f"transport error - {type(exc).__name__}: {exc}", url) from exc
    except ValueError as exc:
        raise PortalError(f"the search endpoint returned non-JSON ({exc})", url) from exc


# ---------------------------------------------------------------------------
# Record construction
# ---------------------------------------------------------------------------


def make_id(portal: str, url: str | None, title: str, reference: str | None = None) -> str:
    """Stable identity for the seen-tenders database.

    Built from the portal plus the most stable identifier available, so the
    same notice is recognised across runs even if its summary text is edited.
    """
    basis = reference or url or title
    digest = hashlib.sha256(f"{portal}|{basis}".encode("utf-8")).hexdigest()[:16]
    return f"{portal}-{digest}"


def build_record(
    portal: str,
    title: str,
    url: str | None = None,
    posted: str | date | None = None,
    closing: str | date | None = None,
    value_text: str | None = None,
    value_usd: float | None = None,
    description: str | None = None,
    eligibility: str | None = None,
    contact: str | None = None,
    notice_type: str | None = None,
    reference: str | None = None,
    default_currency: str | None = None,
) -> dict:
    """Normalise anything a portal produced into the standard record."""
    title = textutil.clean(title)
    description = textutil.clean(description) or None

    if value_usd is None and value_text:
        value_usd = money.parse_value_usd(value_text, default_currency)

    blob = " ".join(p for p in (title, description, eligibility, value_text) if p)
    language = "ar" if textutil.is_arabic(blob) else "en"

    if eligibility:
        eligibility = textutil.clean(eligibility)
    elif textutil.detect_national_only(blob):
        eligibility = config.NATIONAL_ONLY_NOTE

    return {
        "id": make_id(portal, url, title, reference),
        "title": title,
        "portal": portal,
        "url": url,
        "posted_date": parse_date(posted),
        "closing_date": parse_date(closing),
        "estimated_value_usd": value_usd,
        "sector": textutil.guess_sector(title, description),
        "description": description,
        "eligibility": eligibility,
        "contact": textutil.clean(contact) or None,
        "notice_type": textutil.clean(notice_type) or None,
        "language": language,
        "reference": reference,
    }


_URLISH_KEY_RE = re.compile(r"url|link|href|uri", re.I)


def field_anatomy(items: list, limit: int = 40) -> list[str]:
    """Printable report of the fields an API response actually carries.

    The HTML portals have --capture; the API portals had nothing, and the gap
    showed. worldbank.py read its link from _pick("url", "notice_url",
    "pdf_url", "noticeurl") -- four plausible spellings, none of them the one
    the API uses -- so every World Bank row reached the report with no link and
    no complaint. A field that is absent and a field that is empty look
    identical to _pick(), and both look identical to "the notice has no URL".

    So report what is there rather than asking whether a guess was right.
    Fill rate is the column that matters: a key present on 3 of 200 notices is
    not the field you want, however promising its name.
    """
    if not items:
        return ["      (no items -- nothing to describe)"]

    dicts = [i for i in items if isinstance(i, dict)]
    if not dicts:
        return [f"      ({len(items)} items, none of them objects)"]

    fill: dict[str, int] = {}
    sample: dict[str, str] = {}
    for item in dicts:
        for key, value in item.items():
            if value in (None, "", [], {}):
                continue
            fill[key] = fill.get(key, 0) + 1
            if key not in sample:
                sample[key] = textutil.clean(str(value))[:70]

    lines = [f"      {len(dicts)} notices; {len(fill)} fields ever populated"]
    ranked = sorted(fill.items(), key=lambda kv: (-kv[1], kv[0]))
    for key, count in ranked[:limit]:
        # Flag the two things a caller is nearly always hunting for: a link,
        # and an identifier a link could be built from.
        mark = ""
        if _URLISH_KEY_RE.search(key) or sample[key].startswith("http"):
            mark = "  <-- URL-ish"
        lines.append(f"      {key:28} {count:5}/{len(dicts)}  "
                     f"{sample[key]!r}{mark}")
    if len(ranked) > limit:
        lines.append(f"      ... and {len(ranked) - limit} more fields")
    return lines


def row_to_record(portal: str, row: Row, default_currency: str | None = None) -> dict:
    """Turn an extracted Row into a standard record."""
    value_text = row.value_text or row.raw_text
    description = row.description or (
        row.raw_text if row.raw_text != row.title else None
    )
    return build_record(
        portal=portal,
        title=row.title,
        url=row.url,
        posted=row.date_text,
        # Deliberately NOT falling back to date_text: that is the publication
        # date, and treating it as a deadline would mark every notice closed.
        closing=row.closing_text,
        value_text=value_text,
        description=description,
        notice_type=row.extra.get("notice_type"),
        reference=row.reference,
        default_currency=default_currency,
    )


def rows_from_html(html: str, base_url: str, selectors: list[str] | None = None,
                   anchor_hint: str | None = None):
    """Run the cascade, raising PortalError when nothing usable came back."""
    result = extract(html, base_url, selectors, anchor_hint)
    if not result.rows:
        raise PortalError(diagnose(html, []), base_url)
    return result


# How many notices a portal returned BEFORE Jordan filtering.
#
# Without this, a portal reporting "OK: 0" is ambiguous: it could have returned
# nothing, or returned 500 worldwide notices of which none were Jordan. Those
# need completely different fixes, and the first live run cost real time to
# diagnose for exactly this reason. Thread-local because portals run in a
# ThreadPoolExecutor, one thread each.
_scanned = threading.local()


def note_scanned(count: int) -> None:
    _scanned.value = count


def take_scanned() -> int | None:
    """Read and clear the count for the current thread."""
    value = getattr(_scanned, "value", None)
    _scanned.value = None
    return value


def jordan_only(records: list[dict]) -> list[dict]:
    """Keep records that actually refer to Jordan.

    Applied to EVERY portal, including those whose API claims to filter by
    country already. The World Bank API silently ignored countryshortname and
    returned worldwide notices; because that module trusted the parameter and
    skipped this function, the first live report led with a Caribbean education
    project. Never trust a source's own filter -- verify it here.
    """
    note_scanned(len(records))
    kept = []
    for record in records:
        if textutil.mentions_jordan(
            record.get("title"), record.get("description"),
            record.get("eligibility"), url=record.get("url"),
        ):
            kept.append(record)
    return kept
