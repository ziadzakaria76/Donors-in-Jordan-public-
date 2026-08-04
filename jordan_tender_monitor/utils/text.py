"""
Text normalisation and country matching.

The country matcher is the piece that most needs care. Substring matching for
"jordan" also matches Jordanstown (Northern Ireland), and "amman" matches
Ammanford (Wales) -- a live problem on UK Find a Tender, which scans the whole
UK procurement corpus rather than a Jordan-specific feed. Latin terms therefore
match on word boundaries.

Arabic must NOT use word boundaries. Arabic is agglutinative: the definite
article and suffixes attach directly to the stem, so الأردنية ("Jordanian")
legitimately contains الأردن ("Jordan") with no boundary between them. Arabic
terms stay substring-based.
"""

from __future__ import annotations

import re
import unicodedata

from .. import config

# Arabic-Indic (U+0660..) and Extended Arabic-Indic / Persian (U+06F0..) digits.
_ARABIC_DIGITS = {
    **{chr(0x0660 + i): str(i) for i in range(10)},
    **{chr(0x06F0 + i): str(i) for i in range(10)},
}
_ARABIC_DIGIT_RE = re.compile("[" + "".join(_ARABIC_DIGITS) + "]")

# Arabic block, including presentation forms.
_ARABIC_CHAR_RE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_WS_RE = re.compile(r"\s+")
_TAG_RE = re.compile(r"<[^>]+>")


def normalise_arabic_digits(text: str) -> str:
    """Convert Arabic-Indic and Persian digits to ASCII.

    Without this, ١٥ تشرين الأول ٢٠٢٦ fails to parse and the tender lands in
    the undated bucket instead of being scheduled correctly.
    """
    if not text:
        return ""
    return _ARABIC_DIGIT_RE.sub(lambda m: _ARABIC_DIGITS[m.group()], text)


def is_arabic(text: str, threshold: float = 0.20) -> bool:
    """True when a meaningful share of the letters are Arabic script."""
    if not text:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    arabic = sum(1 for c in letters if _ARABIC_CHAR_RE.match(c))
    return (arabic / len(letters)) >= threshold


def strip_tags(html: str) -> str:
    """Crude tag strip for text that has already been extracted from a node."""
    return _TAG_RE.sub(" ", html or "")


def clean(text: str | None) -> str:
    """Collapse whitespace and normalise unicode; safe on None."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = text.replace("‏", "").replace("‎", "")  # RTL/LTR marks
    return _WS_RE.sub(" ", text).strip()


# Named tags only, deliberately. A blanket </?[a-z][^>]*> would also eat
# "<placeholder>", "<your name here>" and "<TBD>" out of prose written by a
# procurement officer, and silently deleting words from a description is a
# worse failure than leaving one stray angle bracket in.
_HTML_TAG_RE = re.compile(
    r"</?(?:p|br|div|span|strong|em|b|i|u|ul|ol|li|dl|dt|dd|table|thead|tbody"
    r"|tr|td|th|h[1-6]|a|font|img|hr|sub|sup|blockquote|pre|code|section"
    r"|article|small|figure|figcaption)\b[^>]*/?>", re.I)


def looks_like_html(text: str | None) -> bool:
    """True when the string carries real HTML markup, not just an angle bracket."""
    return bool(text) and _HTML_TAG_RE.search(str(text)) is not None


def strip_html(text: str | None) -> str:
    """Plain text out of a field that may be HTML; clean() otherwise.

    The World Bank API returns notice_text as raw markup, and this module fed
    it straight into the record description. Every World Bank row in the Word
    and Excel reports therefore read:

        <p><u><strong>Job Title:</strong></u>&nbsp;Databases Administrator</p>

    Nothing failed. The text was all present, in source order, and simply
    unreadable -- and because description also feeds the Jordan matcher and the
    sector guesser, the tags were being scored as if they were words.

    Markup is converted rather than deleted: block tags become spaces, so
    "<p>A</p><p>B</p>" reads "A B" and not "AB", and entities are resolved by
    the parser, so &nbsp; and &rsquo; arrive as the characters they name.

    Tags are stripped BEFORE entities are resolved. The other order would turn
    a source's deliberately escaped "&lt;p&gt;" into a real tag and then delete
    it -- losing text the author took care to show.
    """
    if not text:
        return ""
    if not looks_like_html(text):
        return clean(text)

    from bs4 import BeautifulSoup
    return clean(BeautifulSoup(str(text), "html.parser").get_text(" "))


def truncate(text: str, limit: int) -> str:
    """Trim to `limit` characters on a word boundary, with an ellipsis."""
    text = clean(text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + " …"


def _word_boundary_hit(haystack: str, term: str) -> bool:
    """Word-boundary match, so 'jordan' does not match 'Jordanstown'."""
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", haystack) is not None


def mentions_jordan(*parts: str | None, url: str | None = None) -> bool:
    """True when the supplied text refers to Jordan the country.

    Email addresses are stripped before matching, because a contact address at
    a donor's Jordan office would otherwise make every notice on the page look
    Jordan-related. A .jo domain, however, is treated as positive evidence --
    it is a deliberate country signal rather than an accident of wording.
    """
    blob = " ".join(clean(p) for p in parts if p)
    if url:
        blob += " " + url

    if config.COUNTRY_TLD:
        for candidate in (blob, url or ""):
            if re.search(r"://[^/\s]*" + re.escape(config.COUNTRY_TLD) + r"(?:[/:\s]|$)",
                         candidate, re.IGNORECASE):
                return True
            if re.search(r"(?<!\w)[\w-]+" + re.escape(config.COUNTRY_TLD) + r"(?!\w)",
                         candidate, re.IGNORECASE):
                # e.g. "mit.gov.jo" written as bare text
                if "@" not in candidate.split(config.COUNTRY_TLD)[0][-40:]:
                    return True

    stripped = _EMAIL_RE.sub(" ", blob).lower()

    for term in config.COUNTRY_TERMS_LATIN:
        if _word_boundary_hit(stripped, term.lower()):
            return True

    # Arabic: substring, deliberately. See the module docstring.
    for term in config.COUNTRY_TERMS_ARABIC:
        if term in blob:
            return True

    return False


def keyword_hits(text: str, lexicon: list[str]) -> list[str]:
    """Terms from `lexicon` present in `text`.

    Latin terms use word boundaries where the term is a single word; multi-word
    phrases and Arabic terms use substring matching.
    """
    if not text:
        return []
    lowered = clean(text).lower()
    hits: list[str] = []
    for term in lexicon:
        t = term.lower()
        if _ARABIC_CHAR_RE.search(t) or " " in t or "-" in t:
            if t in lowered:
                hits.append(term)
        elif _word_boundary_hit(lowered, t):
            hits.append(term)
    return hits


def guess_sector(*parts: str | None) -> str:
    """Best-guess sector label. Never used to include or exclude (Q1)."""
    blob = " ".join(clean(p) for p in parts if p).lower()
    if not blob:
        return "Unclassified"
    best, best_score = "Unclassified", 0
    for sector, terms in config.SECTOR_LEXICON.items():
        score = sum(1 for t in terms if t in blob)
        if score > best_score:
            best, best_score = sector, score
    return best


def detect_national_only(*parts: str | None) -> bool:
    """True when the text restricts bidding to national/local firms."""
    blob = " ".join(clean(p) for p in parts if p).lower()
    if not blob:
        return False
    return any(marker.lower() in blob for marker in config.NATIONAL_ONLY_MARKERS)
