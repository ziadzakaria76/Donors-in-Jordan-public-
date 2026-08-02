"""
Contract-value parsing.

Two defects this module exists to prevent, both of which silently delete real
tenders rather than failing loudly:

1. Taking the first number in a row. "Published: 01 August 2026" then parses
   as a value of 1, and against a $100,000 minimum that tender disappears. A
   number is therefore only accepted as a contract value when it carries a
   currency symbol/code or a magnitude word ("million", "k") nearby. The one
   exception is a string that is nothing but a number -- that came from a
   dedicated value field, so it is taken at face value.

2. European number formats. "EUR 1.500.000" is 1.5 million, not 1.5. Getting
   this wrong loses most GIZ and KfW values, and does so by making large
   contracts look tiny -- i.e. by filtering them out.

When several qualifying candidates appear in one string ("EUR 50,000 per year,
total EUR 1,200,000"), the largest is taken as the contract value.
"""

from __future__ import annotations

import re

from .. import config
from .text import normalise_arabic_digits

# Currency symbols and ISO codes we recognise, mapped to the ISO code.
_SYMBOLS = {
    "$": "USD", "US$": "USD", "USD": "USD", "€": "EUR", "EUR": "EUR",
    "£": "GBP", "GBP": "GBP", "JOD": "JOD", "JD": "JOD", "CHF": "CHF",
    "SAR": "SAR", "SR": "SAR", "AED": "AED", "¥": "JPY", "JPY": "JPY",
    "SEK": "SEK", "NOK": "NOK", "DKK": "DKK", "CAD": "CAD", "AUD": "AUD",
    "XDR": "XDR", "SDR": "XDR", "KWD": "KWD",
    "دينار": "JOD", "دولار": "USD", "يورو": "EUR", "ريال": "SAR", "درهم": "AED",
}

# Longest first so "US$" wins over "$" and "SAR" over "SR".
_CURRENCY_RE = re.compile(
    "(" + "|".join(re.escape(k) for k in sorted(_SYMBOLS, key=len, reverse=True)) + ")",
    re.IGNORECASE,
)

# Magnitude words. Bare "m"/"k"/"bn" only count when glued to the number
# (handled separately) to avoid matching stray letters in prose.
_MAGNITUDES = {
    "million": 1e6, "millions": 1e6, "mio": 1e6, "mio.": 1e6, "mn": 1e6,
    "millionen": 1e6, "millionsofusd": 1e6, "مليون": 1e6,
    "billion": 1e9, "billions": 1e9, "bn": 1e9, "milliarden": 1e9, "مليار": 1e9,
    "thousand": 1e3, "tausend": 1e3, "ألف": 1e3, "الف": 1e3,
}
_MAG_SUFFIX_RE = re.compile(r"^\s*(m|k|bn|b)\b", re.IGNORECASE)
_MAG_SUFFIX = {"m": 1e6, "k": 1e3, "bn": 1e9, "b": 1e9}

# A run of digits with optional . , space or NBSP group separators.
_NUMBER_RE = re.compile(r"\d[\d.,   ]*\d|\d")

_PURE_NUMBER_RE = re.compile(r"^\s*\d[\d.,   ]*\d\s*$|^\s*\d\s*$")

# How far either side of a number we look for a currency or magnitude token.
_WINDOW = 18


def normalise_number(token: str) -> float | None:
    """Turn a grouped numeric string into a float, handling both conventions.

    1.500.000 -> 1500000    (dot as thousands, European)
    1,500,000 -> 1500000    (comma as thousands, Anglo)
    1.500,50  -> 1500.50    (comma as decimal, European)
    1,500.50  -> 1500.50    (dot as decimal, Anglo)
    1.50      -> 1.5        (two trailing digits => decimal)
    """
    tok = (token or "").replace(" ", "").replace(" ", "").replace(" ", "").strip()
    if not tok or not tok[0].isdigit():
        return None

    has_dot, has_comma = "." in tok, "," in tok
    try:
        if has_dot and has_comma:
            # Whichever separator comes last is the decimal point.
            if tok.rfind(".") > tok.rfind(","):
                whole, frac = tok.rsplit(".", 1)
                return float(whole.replace(",", "") + "." + frac)
            whole, frac = tok.rsplit(",", 1)
            return float(whole.replace(".", "") + "." + frac)

        sep = "." if has_dot else ("," if has_comma else None)
        if sep is None:
            return float(tok)

        parts = tok.split(sep)
        # Every group after the first being exactly three digits means the
        # separator is a thousands separator. "1.500" is 1500 in a tender
        # notice; a genuine 1.5 would be written "1.50" or "1,5".
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]) and 1 <= len(parts[0]) <= 3:
            return float("".join(parts))
        if len(parts) == 2:
            return float(parts[0] + "." + parts[1])
        return float("".join(parts))
    except ValueError:
        return None


_SYMBOLS_CI = {k.upper(): v for k, v in _SYMBOLS.items()}
_GAP_RE = re.compile(r"[\s:.\-\u2013\u2014()\u00a0]*")


def _lookup(symbol: str) -> str:
    return _SYMBOLS_CI.get(symbol.upper(), "USD")


def _currency_near(text: str, start: int, end: int) -> str | None:
    """Currency code sitting immediately before or after a number.

    "Immediately" means nothing but separators in between, so a currency
    mentioned elsewhere in a long sentence cannot attach itself to an
    unrelated number.
    """
    before = text[max(0, start - _WINDOW):start]
    after = text[end:end + _WINDOW]

    # Closest match wins, so take the last match in the preceding window.
    matches = list(_CURRENCY_RE.finditer(before))
    if matches:
        m = matches[-1]
        if _GAP_RE.fullmatch(before[m.end():] or ""):
            return _lookup(m.group(1))

    m = _CURRENCY_RE.search(after)
    if m and _GAP_RE.fullmatch(after[:m.start()] or ""):
        return _lookup(m.group(1))
    return None


def _magnitude_after(text: str, end: int) -> float:
    """Multiplier from a magnitude word following the number."""
    after = text[end:end + _WINDOW]
    m = _MAG_SUFFIX_RE.match(after)
    if m:
        return _MAG_SUFFIX[m.group(1).lower()]
    word = re.match(r"[\s\-]*([A-Za-zÀ-ÿ؀-ۿ.]+)", after)
    if word:
        key = word.group(1).lower().strip(".")
        if key in _MAGNITUDES:
            return _MAGNITUDES[key]
        if word.group(1).lower() in _MAGNITUDES:
            return _MAGNITUDES[word.group(1).lower()]
    return 1.0


def parse_value(text: str | None, default_currency: str | None = None
                ) -> tuple[float, str] | None:
    """Extract a contract value from free text.

    Returns (amount_in_original_currency, ISO code) or None when the text
    carries no defensible value. Returning None is the correct outcome far more
    often than not -- most donor notices publish no value at all.
    """
    if text is None:
        return None
    raw = normalise_arabic_digits(str(text)).strip()
    if not raw:
        return None

    # A field containing nothing but a number came from a dedicated value
    # field, so there is no ambiguity to guard against.
    if _PURE_NUMBER_RE.match(raw):
        amount = normalise_number(raw)
        if amount is None or amount <= 0:
            return None
        return amount, (default_currency or "USD")

    candidates: list[tuple[float, str]] = []
    for m in _NUMBER_RE.finditer(raw):
        base = normalise_number(m.group())
        if base is None or base <= 0:
            continue
        currency = _currency_near(raw, m.start(), m.end())
        multiplier = _magnitude_after(raw, m.end())

        # The core guard: no currency and no magnitude word means this number
        # is not a contract value. It is a date, a reference number, a lot
        # count or a page number.
        if currency is None and multiplier == 1.0:
            continue
        candidates.append((base * multiplier, currency or default_currency or "USD"))

    if not candidates:
        return None
    # "EUR 50,000 per year, total EUR 1,200,000" -- the largest is the contract.
    return max(candidates, key=lambda c: c[0])


def to_usd(amount: float, currency: str) -> float:
    """Convert to USD using the static table. Ranking only, never financial."""
    return amount * config.FX_TO_USD.get((currency or "USD").upper(), 1.0)


def parse_value_usd(text: str | None, default_currency: str | None = None) -> float | None:
    """Convenience wrapper returning a USD figure, or None."""
    parsed = parse_value(text, default_currency)
    if parsed is None:
        return None
    amount, currency = parsed
    return round(to_usd(amount, currency), 2)


def format_usd(value: float | None) -> str:
    """Human-readable value for reports."""
    if value is None:
        return "Not published"
    if value >= 1_000_000:
        return f"US$ {value / 1_000_000:,.2f}m"
    return f"US$ {value:,.0f}"
