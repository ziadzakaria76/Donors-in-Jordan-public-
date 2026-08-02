"""
Multi-language date parsing.

Donor portals publish dates in whatever their own locale uses. GIZ writes
31.12.2026 and "15. Januar 2027"; the Saudi Fund writes ١٥ تشرين الأول ٢٠٢٦
with Arabic-Indic digits and Levantine month names. A parser that only handles
English silently drops those tenders into the undated bucket, where -- because
undated notices are kept and flagged (Q6) -- they lose their urgency score and
sink in the ranking.

Day-first is the default: 03/04/2026 is 3 April across every European and UN
portal here. ISO strings are detected and parsed unambiguously.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from dateutil import parser as dateparser

from .text import clean, normalise_arabic_digits

# Non-English month names mapped to month number. Levantine Arabic month names
# (تشرين الأول etc.) are used across Jordan, Syria, Lebanon and Iraq; the
# Gregorian transliterations (يناير etc.) are used in the Gulf.
_MONTHS: dict[str, int] = {}


def _add(names: dict[str, int]) -> None:
    for name, num in names.items():
        _MONTHS[name.lower()] = num


_add({  # German
    "januar": 1, "jänner": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
    "oktober": 10, "november": 11, "dezember": 12,
    "jan": 1, "feb": 2, "mär": 3, "mrz": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
})
_add({  # French
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
})
_add({  # Arabic -- Levantine
    "كانون الثاني": 1, "شباط": 2, "آذار": 3, "اذار": 3, "نيسان": 4,
    "أيار": 5, "ايار": 5, "حزيران": 6, "تموز": 7, "آب": 8, "اب": 8,
    "أيلول": 9, "ايلول": 9, "تشرين الأول": 10, "تشرين الاول": 10,
    "تشرين الثاني": 11, "كانون الأول": 12, "كانون الاول": 12,
})
_add({  # Arabic -- Gulf / Gregorian transliteration
    "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4, "مايو": 5,
    "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8, "سبتمبر": 9,
    "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
})

# Longest first so "تشرين الأول" is tried before "تشرين الثاني" cannot shadow it,
# and "كانون الأول" before "آب".
_MONTH_NAMES_SORTED = sorted(_MONTHS, key=len, reverse=True)

# The trailing guard is (?!\d), NOT \b.
#
# \b would require a non-word character after the day, and in "2026-06-01T09:00"
# the next character is "T" -- a word character -- so the boundary fails and the
# whole ISO fast path is skipped. Parsing then falls through to dateutil with
# dayfirst=True, which reads 2026-06-01 as 1 June... as 6 January. Every REST
# API here returns ISO timestamps with a T, so this silently swapped day and
# month on every API-sourced date where both were <= 12, corrupting the
# closing-date filter in both directions: closed tenders looking open, and open
# ones being dropped as closed.
_ISO_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
_DOTTED_RE = re.compile(r"\b(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\b")
_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_DMY_NAMED_RE = re.compile(r"\b(\d{1,2})\s*\.?\s*([^\W\d_]{3,}(?:\s+[^\W\d_]{3,})?)\s+(\d{4})\b",
                           re.UNICODE)
_YEAR_ONLY_RE = re.compile(r"\b(19|20)\d{2}\b")


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date(value: str | date | datetime | None, dayfirst: bool = True) -> date | None:
    """Parse a date from any of the formats these portals publish.

    Returns None when nothing defensible is present. None is a legitimate,
    common outcome -- it means "deadline not published" and the tender is kept
    and flagged rather than dropped.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = clean(normalise_arabic_digits(str(value)))
    if not text:
        return None

    # ISO first -- unambiguous, and what every REST API here returns.
    m = _ISO_RE.search(text)
    if m:
        got = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if got:
            return got

    # Named month in any supported language: "15. Januar 2027",
    # "15 تشرين الأول 2026", "15 October 2026".
    lowered = text.lower()
    for name in _MONTH_NAMES_SORTED:
        idx = lowered.find(name)
        if idx == -1:
            continue
        month = _MONTHS[name]
        before = text[max(0, idx - 12):idx]
        after = text[idx + len(name):idx + len(name) + 12]
        day_m = re.search(r"(\d{1,2})\s*\.?\s*$", before)
        year_m = re.search(r"(\d{4})", after)
        if not day_m:
            day_m = re.search(r"^\s*(\d{1,2})\b", after)
            year_m = re.search(r"(\d{4})", after[day_m.end():]) if day_m else None
        if day_m and year_m:
            got = _safe_date(int(year_m.group(1)), month, int(day_m.group(1)))
            if got:
                return got

    # 31.12.2026 -- German convention, always day-first.
    m = _DOTTED_RE.search(text)
    if m:
        got = _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if got:
            return got

    # 31/12/2026 -- day-first unless that is impossible.
    m = _SLASH_RE.search(text)
    if m:
        a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if dayfirst:
            got = _safe_date(year, b, a) or _safe_date(year, a, b)
        else:
            got = _safe_date(year, a, b) or _safe_date(year, b, a)
        if got:
            return got

    # Last resort: dateutil, which handles English long forms and much else.
    try:
        parsed = dateparser.parse(text, dayfirst=dayfirst, fuzzy=True)
        if parsed:
            return parsed.date()
    except (ValueError, OverflowError, TypeError):
        pass

    return None


def is_open(closing: date | None, today: date | None = None) -> bool:
    """True when a tender is still open.

    A tender closing TODAY is open. An off-by-one here would discard the most
    urgent tenders in the report, which is exactly backwards.
    """
    if closing is None:
        return True  # unknown deadline: kept and flagged, per Q6
    return closing >= (today or date.today())


def days_until(closing: date | None, today: date | None = None) -> int | None:
    if closing is None:
        return None
    return (closing - (today or date.today())).days


def fmt(value: date | None) -> str:
    return value.isoformat() if value else "Not published"
