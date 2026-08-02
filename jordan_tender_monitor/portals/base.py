"""
Shared plumbing for every portal module.

Provides:
  * a polite, retrying HTTP session (2s minimum gap per host, exponential backoff)
  * `make_record()` -- builds the standardised tender dict every scraper returns
  * date / currency / language helpers
  * `PortalError` -- raised when a portal is reachable but unparseable, so the
    orchestrator can report "unavailable - check manually" instead of silently
    returning zero tenders
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import config

log = logging.getLogger(__name__)


class PortalError(RuntimeError):
    """A portal could not be scraped. Message is surfaced in the report."""


# --------------------------------------------------------------------------
# Polite HTTP
# --------------------------------------------------------------------------
_host_locks: dict[str, threading.Lock] = {}
_host_last_call: dict[str, float] = {}
_registry_lock = threading.Lock()

_session = requests.Session()
_session.headers.update(
    {
        "User-Agent": config.USER_AGENT,
        "Accept-Language": "en-GB,en;q=0.9,ar;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    }
)


def _throttle(url: str) -> None:
    """Enforce POLITE_DELAY_SECONDS between requests to the same host."""
    host = urlparse(url).netloc
    with _registry_lock:
        lock = _host_locks.setdefault(host, threading.Lock())
    with lock:
        elapsed = time.monotonic() - _host_last_call.get(host, 0.0)
        wait = config.POLITE_DELAY_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
        _host_last_call[host] = time.monotonic()


_RETRYABLE = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.HTTPError,
    requests.exceptions.ChunkedEncodingError,
)


@retry(
    stop=stop_after_attempt(config.MAX_RETRIES),
    wait=wait_exponential(multiplier=config.RETRY_BASE_DELAY, min=config.RETRY_BASE_DELAY),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
def http_request(method: str, url: str, **kwargs) -> requests.Response:
    """Rate-limited HTTP call with retry + exponential backoff."""
    _throttle(url)
    kwargs.setdefault("timeout", config.REQUEST_TIMEOUT)
    resp = _session.request(method, url, **kwargs)
    # 4xx other than 429 are not worth retrying -- surface them immediately.
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    return resp


def http_get(url: str, **kwargs) -> requests.Response:
    return http_request("GET", url, **kwargs)


def http_post(url: str, **kwargs) -> requests.Response:
    return http_request("POST", url, **kwargs)


def soup_of(markup: str, *, xml: bool = False):
    """
    Parse markup, preferring lxml and falling back to the stdlib parser.

    `xml=True` matters for RSS/Atom: the HTML parser treats <link> as a void
    element, so feed item links come back empty.
    """
    import warnings

    from bs4 import BeautifulSoup

    try:
        from bs4 import XMLParsedAsHTMLWarning

        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    except ImportError:
        pass

    if xml:
        for parser in ("lxml-xml", "xml"):
            try:
                return BeautifulSoup(markup, parser)
            except Exception:
                continue
    try:
        return BeautifulSoup(markup, "lxml")
    except Exception:
        return BeautifulSoup(markup, "html.parser")


# --------------------------------------------------------------------------
# Field helpers
# --------------------------------------------------------------------------
_ARABIC_RE = re.compile(r"[؀-ۿ]")
_WS_RE = re.compile(r"\s+")


def clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(v) for v in value if v)
    if isinstance(value, dict):
        # TED and some APIs return {"eng": "..."} language maps
        for key in ("eng", "en", "ENG", "value", "text"):
            if key in value:
                return clean_text(value[key])
        value = " ".join(str(v) for v in value.values() if v)
    return _WS_RE.sub(" ", str(value)).strip()


def detect_language(*texts: str) -> str:
    """Return 'ar' if the text is meaningfully Arabic, else 'en'."""
    blob = " ".join(t for t in texts if t)
    if not blob:
        return "en"
    arabic = len(_ARABIC_RE.findall(blob))
    letters = sum(1 for ch in blob if ch.isalpha())
    if letters and arabic / letters > 0.25:
        return "ar"
    return "en"


_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
    "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%Y/%m/%d",
    "%d.%m.%Y", "%d. %B %Y", "%Y%m%d", "%d %B, %Y", "%b %d %Y", "%d/%m/%y",
]

# Arabic-Indic and Persian digits -> ASCII. GIZ/KfW publish German dates and
# SFD/ADFD publish Arabic ones, so neither parses without this step.
_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_LATIN_MONTHS = {
    # German (GIZ, KfW)
    "januar": "January", "februar": "February", "märz": "March", "maerz": "March",
    "mai": "May", "juni": "June", "juli": "July", "oktober": "October",
    "dezember": "December", "dez": "Dec", "okt": "Oct", "mrz": "Mar",
    # French (EIB, some EU notices)
    "janvier": "January", "février": "February", "fevrier": "February",
    "mars": "March", "avril": "April", "mai_fr": "May", "juin": "June",
    "juillet": "July", "août": "August", "aout": "August",
    "septembre": "September", "octobre": "October", "novembre": "November",
    "décembre": "December", "decembre": "December",
}

_ARABIC_MONTHS = {
    "كانون الثاني": "January", "يناير": "January",
    "شباط": "February", "فبراير": "February",
    "آذار": "March", "اذار": "March", "مارس": "March",
    "نيسان": "April", "أبريل": "April", "ابريل": "April",
    "أيار": "May", "ايار": "May", "مايو": "May",
    "حزيران": "June", "يونيو": "June",
    "تموز": "July", "يوليو": "July",
    "آب": "August", "أغسطس": "August", "اغسطس": "August",
    "أيلول": "September", "ايلول": "September", "سبتمبر": "September",
    "تشرين الأول": "October", "تشرين الاول": "October", "أكتوبر": "October",
    "تشرين الثاني": "November", "نوفمبر": "November",
    "كانون الأول": "December", "كانون الاول": "December", "ديسمبر": "December",
}


def normalise_datetext(text: str) -> str:
    """ASCII digits and English month names, so strptime has a chance."""
    text = text.translate(_DIGIT_MAP)
    # Arabic month names first -- longest match wins ("كانون الأول" before "آب")
    for arabic in sorted(_ARABIC_MONTHS, key=len, reverse=True):
        if arabic in text:
            text = text.replace(arabic, _ARABIC_MONTHS[arabic])
    for alias, english in _LATIN_MONTHS.items():
        if alias.endswith("_fr"):
            continue
        text = re.sub(rf"(?<![^\W\d_]){re.escape(alias)}(?![^\W\d_])",
                      english, text, flags=re.IGNORECASE)
    return text


def parse_date(value) -> str | None:
    """Best-effort date parse -> ISO 8601 date string, or None."""
    if value in (None, "", "null"):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = clean_text(value)
    if not text:
        return None
    text = normalise_datetext(text)
    # Strip a trailing timezone name and normalise the 'Z' suffix
    text = re.sub(r"\s*\((?:UTC|GMT)[^)]*\)", "", text).strip()
    candidate = text.replace("Z", "+0000")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            continue
    # Fall back to fromisoformat, which handles most ISO variants
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    # Last resort: find a bare date inside a longer string
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if m:
        try:
            return datetime(int(m[1]), int(m[2]), int(m[3])).date().isoformat()
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", text)
    if m:
        try:
            return datetime(int(m[3]), int(m[2]), int(m[1])).date().isoformat()
        except ValueError:
            return None
    return None


_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
_VALUE_RE = re.compile(
    r"(?P<cur>USD|EUR|GBP|JOD|CHF|SAR|AED|JPY|SEK|NOK|DKK|CAD|AUD|XDR|\$|€|£|¥)?"
    r"\s*(?P<num>\d[\d,.\s]*\d|\d)"
    r"\s*(?P<mult>million|billion|mn|bn|m|k)?"
    r"\s*(?P<cur2>USD|EUR|GBP|JOD|CHF|SAR|AED|JPY|SEK|NOK|DKK|CAD|AUD|XDR)?",
    re.IGNORECASE,
)


def parse_value_usd(value) -> float | None:
    """Extract a contract value from free text or a number and convert to USD."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if value > 0 else None

    text = clean_text(value).translate(_DIGIT_MAP)
    if not text:
        return None

    # A bare numeric string is taken at face value; anything embedded in prose
    # must carry a currency or a magnitude word. Without this guard, free row
    # text such as "Published: 01 August 2026" parses as a value of 1.
    bare = bool(_BARE_NUMBER_RE.fullmatch(text.strip()))
    candidates: list[float] = []
    for match in _VALUE_RE.finditer(text):
        if not bare and not (match.group("cur") or match.group("cur2") or match.group("mult")):
            continue
        converted = _convert_value_match(match)
        if converted is not None:
            candidates.append(converted)
    if not candidates:
        return None
    # Row text often carries several figures (lot values, fees, reference
    # numbers). The contract value is reliably the largest of them.
    return max(candidates)


_BARE_NUMBER_RE = re.compile(r"[\d,.\s]+")


def _convert_value_match(m) -> float | None:
    """Convert one regex match into USD, honouring both separator conventions."""

    raw = m.group("num").replace(" ", "").replace(" ", "")
    mult_hint = bool(m.group("mult"))
    # Decide whether "," and "." are thousands separators or a decimal point.
    # Both conventions appear: "1,500,000" (UK/US) and "1.500.000" (DE/EU).
    if "," in raw and "." in raw:
        # Whichever appears last is the decimal separator
        raw = (raw.replace(",", "") if raw.rfind(".") > raw.rfind(",")
               else raw.replace(".", "").replace(",", "."))
    elif "," in raw:
        parts = raw.split(",")
        raw = raw.replace(",", "") if all(len(p) == 3 for p in parts[1:]) else raw.replace(",", ".")
    elif "." in raw:
        parts = raw.split(".")
        if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
            raw = raw.replace(".", "")           # 1.500.000 -> 1500000
        elif len(parts) == 2 and len(parts[1]) == 3 and not mult_hint:
            raw = raw.replace(".", "")           # 750.000 -> 750000, but "1.2 million" stays decimal
    try:
        amount = float(raw)
    except ValueError:
        return None
    if amount <= 0:
        return None

    mult = (m.group("mult") or "").lower()
    amount *= {"million": 1e6, "mn": 1e6, "m": 1e6,
               "billion": 1e9, "bn": 1e9, "k": 1e3}.get(mult, 1)

    cur = (m.group("cur") or m.group("cur2") or "USD").upper()
    cur = _CURRENCY_SYMBOLS.get(cur, cur)
    return round(amount * config.FX_TO_USD.get(cur, 1.0), 2)


def guess_sector(*texts: str) -> str | None:
    """Label a tender with its best-matching sector (report annotation only)."""
    blob = " ".join(t for t in texts if t).lower()
    if not blob:
        return None
    best, best_hits = None, 0
    for sector, terms in config.SECTOR_LEXICON.items():
        hits = sum(1 for term in terms if term in blob)
        if hits > best_hits:
            best, best_hits = sector, hits
    return best


_EMAIL_RE = re.compile(r"\S+@\S+")
_JO_DOMAIN_RE = re.compile(r"\.jo\b")
_country_matchers: tuple | None = None


def _build_country_matchers() -> tuple:
    """
    Latin terms match on word boundaries; Arabic terms match as substrings.

    Boundaries matter: plain `"jordan" in text` also fires on Jordanstown
    (Northern Ireland), Ammanford (Wales) and any contact named Jordan, which
    would pollute the FCDO feed in particular -- that one scans the whole UK
    notice corpus. Arabic cannot use boundaries because it is agglutinative:
    الأردنية ("Jordanian") legitimately contains الأردن ("Jordan").
    """
    latin = [t.lower() for t in config.COUNTRY_TERMS if t.isascii()]
    arabic = [t for t in config.COUNTRY_TERMS if not t.isascii()]
    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(t) for t in sorted(latin, key=len, reverse=True)) + r")\b"
    ) if latin else None
    return pattern, arabic


def mentions_jordan(*texts: str) -> bool:
    global _country_matchers
    blob = " ".join(t for t in texts if t)
    if not blob:
        return False

    # A .jo address or domain is strong evidence, so test before stripping emails
    if _JO_DOMAIN_RE.search(blob.lower()):
        return True
    # Contact addresses name people, not countries (jordan.smith@contractor.co.uk)
    blob = _EMAIL_RE.sub(" ", blob)

    if _country_matchers is None:
        _country_matchers = _build_country_matchers()
    pattern, arabic = _country_matchers
    if pattern and pattern.search(blob.lower()):
        return True
    return any(term in blob for term in arabic)


def make_id(portal: str, title: str, url: str = "", native_id: str = "") -> str:
    """Stable unique ID: the source's own ID where available, else a hash."""
    if native_id:
        return f"{portal}:{clean_text(native_id)}"
    digest = hashlib.sha1(
        f"{portal}|{clean_text(title).lower()}|{clean_text(url)}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{portal}:{digest}"


def make_record(
    *,
    portal_key: str,
    title: str,
    url: str = "",
    native_id: str = "",
    posted_date=None,
    closing_date=None,
    estimated_value=None,
    sector: str | None = None,
    description: str = "",
    eligibility: str | None = None,
    contact: str | None = None,
    notice_type: str | None = None,
    language: str | None = None,
) -> dict:
    """Build the standardised tender dict returned by every scraper."""
    title = clean_text(title)
    description = clean_text(description)
    portal = config.PORTAL_NAMES.get(portal_key, portal_key)
    return {
        "id": make_id(portal_key, title, url, native_id),
        "title": title,
        "portal": portal,
        "portal_key": portal_key,
        "url": clean_text(url),
        "posted_date": parse_date(posted_date),
        "closing_date": parse_date(closing_date),
        "estimated_value_usd": parse_value_usd(estimated_value),
        "sector": sector or guess_sector(title, description),
        "description": description,
        "eligibility": clean_text(eligibility) or None,
        "contact": clean_text(contact) or None,
        "notice_type": clean_text(notice_type) or None,
        "language": language or detect_language(title, description),
    }


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
