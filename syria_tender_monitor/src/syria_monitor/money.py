"""Contract value parsing.

A wrong value is worse than no value: against a minimum-value filter it deletes
real tenders silently. Every rule here exists because the naive version fails.
r"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

# Anything below this is a misread (a date fragment, a lot number, a page
# count); anything above it is a misread too. An incoherent value means
# MISSING, never DISQUALIFIED — a tender is never deleted for it.
MIN_PLAUSIBLE = 1_000.0
MAX_PLAUSIBLE = 5_000_000_000.0

_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "US$": "USD", "SY£": "SYP", "ل.س": "SYP"}
_CODES = ("USD", "EUR", "GBP", "CHF", "JPY", "SDG", "TRY", "SYP", "JOD", "LBP", "AED", "SAR")

_MAGNITUDES = {
    "k": 1_000, "thousand": 1_000, "tausend": 1_000, "mille": 1_000, "ألف": 1_000,
    "m": 1_000_000, "mn": 1_000_000, "mio": 1_000_000, "million": 1_000_000,
    "millions": 1_000_000, "millionen": 1_000_000, "مليون": 1_000_000,
    "bn": 1_000_000_000, "billion": 1_000_000_000, "milliarden": 1_000_000_000,
    "مليار": 1_000_000_000,
}

_NUMBER = r"\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_MAG = r"(?:k|mn?|mio\.?|bn|thousand|tausend|mille|million[es]?|millionen|billion|milliarden|ألف|مليون|مليار)"
_CANDIDATE = re.compile(
    r"(?P<pre>US\$|SY£|[$€£]|ل\.س|\b(?:%s)\b)?\s*"
    r"(?P<num>%s)\s*"
    r"(?P<mag>%s)?\s*"
    r"(?P<post>US\$|SY£|[$€£]|ل\.س|\b(?:%s)\b)?" % ("|".join(_CODES), _NUMBER, _MAG, "|".join(_CODES)),
    re.IGNORECASE,
)


@dataclass
class ParsedValue:
    amount: Optional[float] = None
    currency: Optional[str] = None
    raw: Optional[str] = None
    flags: list[str] = field(default_factory=list)

    @property
    def published(self) -> bool:
        return self.amount is not None


def parse_number(token: str) -> Optional[float]:
    """Handle European and Anglo grouping.

    EUR 1.500.000 is 1.5 million, not 1.5 — get this wrong and most GIZ and KfW
    values are lost.
    r"""
    t = token.strip().replace(" ", "").replace(" ", "")
    if not t:
        return None
    has_dot, has_comma = "." in t, "," in t
    try:
        if has_dot and has_comma:
            # Whichever separator comes last is the decimal separator.
            if t.rfind(",") > t.rfind("."):
                t = t.replace(".", "").replace(",", ".")
            else:
                t = t.replace(",", "")
        elif has_comma:
            # 1,5 -> decimal; 1,500 / 1,500,000 -> thousands
            t = t.replace(",", ".") if re.fullmatch(r"\d+,\d{1,2}", t) else t.replace(",", "")
        elif has_dot:
            t = t if re.fullmatch(r"\d+\.\d{1,2}", t) else t.replace(".", "")
        return float(t)
    except ValueError:
        return None


def parse_value(text: Optional[str], published: Optional[date] = None,
                profile: Optional[dict] = None) -> ParsedValue:
    """Pull a contract value out of free text.

    Requires a currency marker or a magnitude word: taking the first number in a
    row turns "Published: 01 August 2026" into a value of $1, which against a
    minimum-value filter silently deletes a real tender. Where several
    candidates qualify, the largest is the contract value.
    """
    result = ParsedValue()
    if not text:
        return result

    best: Optional[tuple[float, str, str]] = None
    for m in _CANDIDATE.finditer(str(text)):
        marker = (m.group("pre") or m.group("post") or "").strip()
        mag_token = (m.group("mag") or "").strip().lower().rstrip(".")
        if not marker and not mag_token:
            continue                      # no currency, no magnitude -> not a value
        number = parse_number(m.group("num"))
        if number is None:
            continue
        if mag_token:
            number *= _MAGNITUDES.get(mag_token, _MAGNITUDES.get(mag_token[0], 1))
        currency = _SYMBOLS.get(marker) or (marker.upper() if marker else None)
        if best is None or number > best[0]:
            best = (number, currency, m.group(0).strip())

    if best is None:
        return result

    amount, currency, raw = best
    result.raw, result.currency = raw, currency

    if not (MIN_PLAUSIBLE <= amount <= MAX_PLAUSIBLE):
        # Not a small tender — a parsing error. Report as unpublished + flagged.
        result.flags.append(f"value_implausible:{amount:g}")
        return result

    result.amount = amount

    if currency and profile:
        result.flags.extend(_currency_flags(currency, published, profile))
    return result


def _currency_flags(currency: str, published: Optional[date], profile: dict) -> list[str]:
    """Flag the redenomination ambiguity. This is a 100x trap, and date-dependent.

    Syria redenominated on 1 January 2026, cutting two zeros (100 old = 1 new)
    with a 90-day dual-circulation window. The same numeral means two different
    amounts depending on when the notice was published, and neither reading
    announces itself as wrong. Worse, a 100x error usually still lands inside
    the plausibility band above — that guard catches nonsense, and this produces
    numbers that look entirely reasonable.

    So: no conversion by default. Report the original currency and amount with
    the ambiguity flagged. A blank a reader knows to check beats a confident
    wrong number.
    """
    cfg = profile.get("currency") or {}
    if currency.upper() != str(cfg.get("code", "")).upper():
        return []

    flags = ["currency_local:no_usd_conversion"]
    redenom = cfg.get("redenomination_date")
    dual_end = cfg.get("dual_circulation_ends")
    if isinstance(redenom, date):
        if published is None:
            flags.append("syp_redenomination_ambiguous:publication_date_unknown")
        elif published < redenom:
            flags.append(f"syp_pre_redenomination:published_{published.isoformat()}")
        elif isinstance(dual_end, date) and published <= dual_end:
            flags.append(f"syp_dual_circulation:published_{published.isoformat()}")
    if cfg.get("convert_to_usd"):
        flags.append("syp_conversion_enabled_check_rate_source")
    return flags
