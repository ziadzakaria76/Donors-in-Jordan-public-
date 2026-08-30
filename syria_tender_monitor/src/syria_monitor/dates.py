"""Date parsing.

Three traps live here. All three corrupt dates without ever raising: the run
reports success and open tenders quietly vanish.
r"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Iterable, Optional

from dateutil import parser as dateparser

# --- trap 1 -----------------------------------------------------------------
# The ISO fast path needs a (?!\d) guard, NOT \b.
#
# Every REST API here returns ISO timestamps with a T: 2026-06-01T09:00. After
# the day the next character is "T", which IS a word character, so \b fails, the
# ISO branch is skipped, and parsing falls through to dateutil with
# dayfirst=True — which reads 2026-06-01 as 6 January instead of 1 June. That
# silently swaps day and month on every API-sourced date where both numbers are
# <= 12 (roughly a third of the calendar) and corrupts the closing-date filter
# in BOTH directions at once: closed tenders shown as open, open ones dropped.
_ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?!\d)")

# --- trap 2 -----------------------------------------------------------------
# A relative countdown between a closing label and a date must void the match.
# UNGM writes a countdown ("Expires in 38 days") between the real deadline and
# the publication date; a naive "find the closing label, take the next date"
# starts at "Expires", runs forward, and lands on the publication date. Every
# notice then carries a deadline months earlier than the real one — and a
# deadline in the past is dropped as closed, so the portal's entire open
# pipeline disappears with nothing to indicate anything went wrong.
_COUNTDOWN_RE = re.compile(
    r"(?:\b(?:in|within|after|for)\b\s*)?\b\d+\s*"
    r"(?:hour|hours|day|days|week|weeks|month|months|year|years|"
    r"stunde|stunden|tag|tage|tagen|woche|wochen|monat|monate|monaten|jahr|jahre|"
    r"jour|jours|semaine|semaines|mois|an|ans|année|années|"
    r"ساعة|يوم|أيام|أسبوع|شهر|أشهر|سنة)\b",
    re.IGNORECASE,
)

ARABIC_INDIC = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
ARABIC_INDIC.update({ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")})

MONTHS = {
    # German
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
    # French
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "décembre": 12, "decembre": 12,
    # Arabic — Levantine usage (Syria, Lebanon, Iraq, Jordan)
    "كانون الثاني": 1, "شباط": 2, "آذار": 3, "اذار": 3, "نيسان": 4,
    "أيار": 5, "ايار": 5, "حزيران": 6, "تموز": 7, "آب": 8, "اب": 8, "أيلول": 9, "ايلول": 9,
    "تشرين الأول": 10, "تشرين الاول": 10, "تشرين الثاني": 11, "كانون الأول": 12, "كانون الاول": 12,
    # Arabic — Gulf/Egyptian usage, which differs and must also work
    "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4, "مايو": 5,
    "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8, "سبتمبر": 9,
    "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}

_DMY_NAMED = re.compile(r"(\d{1,2})\s*\.?\s*([^\W\d_]{3,}(?:\s+[^\W\d_]{3,})?)\s*\.?\s*(\d{4})", re.UNICODE)
_DOTTED = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
# THE MONTH HAS TO BE A MONTH. This used [^\W\d_]{3,} -- any word of three or
# more letters -- which reads "10 Sub 10" as a date shape, and a navigation menu
# of "Section 10 / Sub 10" items then looks half-dated. A four-digit year was
# hiding that: loosening the year to two digits, which UNDP needs, took the nav
# fixture's quality from 0.35 to 0.57 and accepted a menu as a listing.
#
# So the month token is drawn from the same MONTHS vocabulary parse_date uses,
# longest first so "januar" cannot be truncated to "jan". That is strictly
# narrower than before AND admits the two-digit years that were being missed:
# UNDP writes "Deadline 01-Sep-26", which this scanner never saw, so every UNDP
# notice reached the report with no closing date at all.
# MONTHS IS NOT A LIST OF MONTH NAMES. It is the lookup parse_date needs for
# the languages dateutil cannot read, so it holds "januar" and "janvier" and no
# "january" at all -- English goes through dateutil's fuzzy fallback instead.
# Building this alternation from MONTHS alone therefore stopped "15 January
# 2026" being a date, which is the commonest date format there is, and the
# first version of this did exactly that. It went unnoticed because the test
# used "September 1, 2026", and September is spelled the same in English,
# German and Dutch, so it is in MONTHS by accident of spelling.
#
# A PREFIX OF A MONTH IS A MONTH. Sources abbreviate at whatever length suits
# them -- Jan, Sept, janv, févr, juil, Okt, Mär -- so rather than list the
# abbreviations and keep discovering missing ones, every prefix of three or
# more characters counts. That is still far narrower than the [^\W\d_]{3,} this
# replaced, which read "10 Sub 10" as a date and let a navigation menu score as
# a listing.
_MONTH_NAMES = set(MONTHS) | {
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
}

_MONTH_FORMS = {name[:length]
                for name in _MONTH_NAMES
                for length in range(3, len(name) + 1)}

# Longest first, so "janvier" is preferred over "jan" and the match does not
# stop three characters in.
_MONTH_ALT = "|".join(re.escape(form) for form in
                      sorted(_MONTH_FORMS, key=len, reverse=True))

_DATE_SHAPED = re.compile(
    r"\d{4}-\d{2}-\d{2}(?!\d)"
    r"|\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"
    r"|\d{1,2}[\s-](?:%s)[\s-]\d{2,4}"
    r"|(?:%s)\s+\d{1,2},?\s+\d{4}" % (_MONTH_ALT, _MONTH_ALT),
    re.UNICODE | re.IGNORECASE,
)

CLOSING_LABELS = ("deadline", "closing date", "closing", "closes", "submission deadline",
                  "date de clôture", "abgabefrist", "schlusstermin",
                  "الموعد النهائي", "آخر موعد", "expires", "expiry", "valid until")


def normalise_digits(text: str) -> str:
    """Arabic-Indic and Eastern-Arabic digits to ASCII."""
    return text.translate(ARABIC_INDIC)


def parse_date(value, dayfirst: bool = True) -> Optional[date]:
    """Parse one date. Returns None rather than guessing.r"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = normalise_digits(str(value)).strip()
    if not text:
        return None

    # ISO first, with the (?!\d) guard so a trailing T does not defeat it.
    m = _ISO_RE.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m = _DOTTED.search(text)          # 31.12.2026 — always day-first
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None

    m = _DMY_NAMED.search(text)       # 15. Januar 2027 / 15 تشرين الأول 2026
    if m:
        month = MONTHS.get(m.group(2).strip().lower())
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(1)))
            except ValueError:
                return None

    try:
        return dateparser.parse(text, dayfirst=dayfirst, fuzzy=True).date()
    except (ValueError, OverflowError, TypeError):
        return None


def find_labelled_date(text: str, labels: Iterable[str] = CLOSING_LABELS,
                       window: int = 120) -> Optional[date]:
    """Find the date belonging to a closing label, refusing countdown matches.

    Labels are tried in the order given, so an explicit "Deadline:" wins over a
    countdown-style "Expires". Any candidate whose gap from the label contains a
    relative duration ("in 38 days") is voided — that text is a countdown, and
    the date after it belongs to something else entirely.
    """
    if not text:
        return None
    haystack = normalise_digits(text)
    lowered = haystack.lower()

    for label in labels:
        start = 0
        while True:
            idx = lowered.find(label.lower(), start)
            if idx == -1:
                break
            start = idx + len(label)
            segment = haystack[start:start + window]
            m = _DATE_SHAPED.search(segment)
            if not m:
                continue
            gap = segment[:m.start()]
            if _COUNTDOWN_RE.search(gap):
                continue                      # countdown, not this label's date
            parsed = parse_date(m.group(0))
            if parsed:
                return parsed
    return None


def is_open(closing: Optional[date], today: Optional[date] = None) -> bool:
    """A deadline of today is OPEN, not expired."""
    if closing is None:
        return True                            # unknown deadline is kept + flagged
    return closing >= (today or date.today())
