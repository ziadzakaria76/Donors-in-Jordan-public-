"""
Class-independent HTML extraction.

Donor sites redesign without notice, and a scraper pinned to CSS class names is
one relaunch away from silently returning nothing -- which looks exactly like a
quiet week. Every page therefore runs through a cascade of six layers, and the
first layer whose rows score as a genuine notice listing wins:

  1. RSS / Atom feed        -- a published contract, survives redesigns
  2. Embedded JSON          -- JSON-LD, __NEXT_DATA__, drupalSettings
  3. CSS selectors          -- fast while the markup holds
  4. Header-aware tables    -- map Deadline/Published/Value columns to fields
  5. Structural inference   -- the repeated sibling block, ignoring classes
  6. Anchor URL pattern     -- last resort

Layers 1, 2 and 5 use no class names at all.

THE QUALITY GATE IS THE POINT. Selectors (layer 3) run before the
class-independent layers, so an over-broad guess like bare `article` or
`table tbody tr` will happily match a navigation menu or a related-documents
table and short-circuit the layer that would actually have worked. Each layer's
rows are therefore scored for "listing-likeness" and must clear a threshold to
win. Carrying a parseable date is weighted most heavily, because that is what
separates a notice listing from a nav menu. If no layer clears the bar, the
best-scoring layer is returned rather than nothing -- a weak result the caller
can see beats a silent zero.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# The cascade deliberately feeds every layer the same content, so the HTML
# layers legitimately see an RSS document when the feed layer is the right one.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from ..utils.dates import parse_date
from ..utils.text import clean

# ---------------------------------------------------------------------------
# Row model
# ---------------------------------------------------------------------------


@dataclass
class Row:
    """One candidate notice, before it is normalised into a tender record."""

    title: str = ""
    url: str | None = None
    date_text: str | None = None
    closing_text: str | None = None
    value_text: str | None = None
    description: str | None = None
    reference: str | None = None
    raw_text: str = ""
    extra: dict = field(default_factory=dict)

    def blob(self) -> str:
        return " ".join(
            p for p in (self.title, self.description, self.raw_text,
                        self.reference, self.value_text) if p
        )


@dataclass
class LayerResult:
    layer: str
    rows: list[Row]
    quality: float = 0.0
    note: str = ""


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------

# Titles that mean "this is the site chrome, not the listing".
_NAV_WORDS = {
    "home", "about", "about us", "contact", "contact us", "login", "log in",
    "sign in", "register", "search", "menu", "next", "previous", "back",
    "skip to main content", "privacy", "cookies", "terms", "sitemap",
    "newsletter", "careers", "faq", "help", "more", "read more", "download",
    "share", "print", "english", "français", "deutsch", "العربية",
    "accessibility", "legal notice", "imprint", "subscribe", "follow us",
}

_MIN_TITLE_LEN = 12
QUALITY_THRESHOLD = 0.36


def _title_is_navish(title: str) -> bool:
    t = clean(title).lower().strip(" .:|-–")
    if not t:
        return True
    if t in _NAV_WORDS:
        return True
    if len(t) < _MIN_TITLE_LEN and not any(ch.isdigit() for ch in t):
        return True
    return False


def score_rows(rows: list[Row]) -> float:
    """Score 0..1 for how much these rows look like a real notice listing.

    A date carries the most weight deliberately. Navigation menus, breadcrumb
    trails and related-document tables all have titles and links; what they do
    not have is a publication or closing date on every row.
    """
    if not rows:
        return 0.0
    n = len(rows)

    with_title = sum(1 for r in rows if not _title_is_navish(r.title))
    with_date = sum(1 for r in rows
                    if parse_date(r.closing_text) or parse_date(r.date_text)
                    or _looks_dated(r.raw_text))
    with_url = sum(1 for r in rows if r.url)
    distinct = len({clean(r.title).lower() for r in rows if r.title})

    title_frac = with_title / n
    date_frac = with_date / n
    url_frac = with_url / n
    distinct_frac = (distinct / n) if n else 0.0

    score = (0.45 * date_frac + 0.25 * title_frac
             + 0.15 * url_frac + 0.15 * distinct_frac)

    # A hard gate on dates, not just a heavy weight.
    #
    # Weighting alone is not enough: a navigation block of four promo panels
    # scores 1.0 on titles, links and distinctness, which reaches 0.55 on
    # weights alone and sails past the threshold while carrying no dates at
    # all. Every real notice listing dates its rows; almost no nav menu does.
    # So a low date fraction multiplies the whole score down rather than
    # merely failing to add to it.
    if date_frac == 0:
        score *= 0.30
    elif date_frac < 0.25:
        score *= 0.45
    elif date_frac < 0.50:
        score *= 0.75

    # Two rows could be anything; a listing usually has several.
    if n < 3:
        score *= 0.75
    return round(min(score, 1.0), 4)


def _drop_navish(rows: list[Row]) -> list[Row]:
    """Remove rows whose title is site chrome rather than a notice.

    Applied to the class-independent layers, where a repeated-sibling match can
    legitimately pick up a trailing "About | Contact" paragraph alongside the
    real rows. Left in place, that becomes a phantom tender.
    """
    return [r for r in rows if not _title_is_navish(r.title)]


_DATE_HINT_RE = re.compile(
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}\s+\w{3,}\s+\d{4}\b|[٠-٩]{1,2}\s",
)


def _looks_dated(text: str) -> bool:
    return bool(text) and bool(_DATE_HINT_RE.search(text))


# ---------------------------------------------------------------------------
# Failure diagnosis -- these need different fixes, so they are named apart
# ---------------------------------------------------------------------------

_BOT_MARKERS = [
    "cloudflare", "cf-browser-verification", "checking your browser",
    "incapsula", "_incapsula_resource", "access denied", "attention required",
    "captcha", "ddos protection", "please enable javascript and cookies",
    "request unsuccessful", "akamai", "bot detection",
]
_JS_SHELL_MARKERS = [
    "you need to enable javascript", "enable javascript to run this app",
    "__next_data__", "ng-app", "id=\"root\"", "id='root'", "id=\"app\"",
    "noscript",
]


def diagnose(html: str, rows: list[Row]) -> str:
    """Name the failure class, because each one needs a different fix."""
    if rows:
        return "ok"
    if not html:
        return "transport error - no content returned (check the URL or host access)"

    low = html.lower()
    if any(m in low for m in _BOT_MARKERS):
        return "bot wall (Cloudflare/Incapsula) - needs a different network or Playwright"

    text_len = len(clean(BeautifulSoup(html, "html.parser").get_text(" ")))
    if text_len < 600 and any(m in low for m in _JS_SHELL_MARKERS):
        return "JavaScript shell - content is rendered client-side; run: playwright install chromium"
    if text_len < 250:
        return "JavaScript shell or empty response - almost no text in the HTML"

    return "layout change - the page loaded but no layer found a listing; run --capture to inspect"


# ---------------------------------------------------------------------------
# Layer 1 -- RSS / Atom
# ---------------------------------------------------------------------------


def _find_ci(node, *names):
    """Find a child tag by name, case-insensitively.

    BeautifulSoup's XML parser preserves case, so a search for 'pubdate' will
    not match <pubDate>. Every feed in the wild uses the camelCase spelling.
    """
    wanted = {n.lower() for n in names}
    for child in node.find_all(True, recursive=True):
        if child.name and child.name.lower().split(":")[-1] in wanted:
            return child
    return None


def _all_ci(soup, *names):
    wanted = {n.lower() for n in names}
    return [t for t in soup.find_all(True)
            if t.name and t.name.lower().split(":")[-1] in wanted]


def extract_feed(content: str, base_url: str = "") -> LayerResult:
    """Parse an RSS or Atom feed.

    Parsed as XML, not HTML. Under an HTML parser BeautifulSoup treats <link>
    as a void element, so <link>https://…</link> yields an empty string and
    every notice loses its URL.
    """
    rows: list[Row] = []
    if not content or "<" not in content:
        return LayerResult("feed", rows, 0.0, "not XML")
    try:
        soup = BeautifulSoup(content, "xml")
    except Exception:
        return LayerResult("feed", rows, 0.0, "XML parse failed")

    items = _all_ci(soup, "item", "entry")
    for item in items:
        title_tag = _find_ci(item, "title")
        title = clean(title_tag.get_text() if title_tag else "")

        # Atom puts the URL in link/@href; RSS puts it in the element text.
        url = None
        for link in _all_ci(item, "link"):
            href = link.get("href") or clean(link.get_text())
            if href:
                url = urljoin(base_url, href)
                break
        if not url:
            guid = _find_ci(item, "guid", "id")
            if guid:
                text = clean(guid.get_text())
                if text.startswith("http"):
                    url = text

        date_tag = _find_ci(item, "pubDate", "published", "updated", "date")
        desc_tag = _find_ci(item, "description", "summary", "content")

        if not title:
            continue
        rows.append(Row(
            title=title,
            url=url,
            date_text=clean(date_tag.get_text()) if date_tag else None,
            description=clean(desc_tag.get_text()) if desc_tag else None,
            raw_text=clean(item.get_text(" ")),
        ))

    return LayerResult("feed", rows, score_rows(rows))


# ---------------------------------------------------------------------------
# Layer 2 -- embedded JSON
# ---------------------------------------------------------------------------

# schema.org types that describe the SITE, not a notice. Nearly every page
# embeds {"@type":"Organization","name":…,"url":…}; accepting those fills the
# report with phantom notices named after the donor.
_SITE_TYPES = {
    "organization", "website", "webpage", "breadcrumblist", "sitenavigationelement",
    "searchaction", "imageobject", "logo", "collegeoruniversity", "corporation",
    "governmentorganization", "ngo", "person", "contactpoint", "postaladdress",
    "wpheader", "wpfooter", "itemlist",
}

_TITLE_KEYS = ("title", "name", "headline", "noticetitle", "subject",
               "projectname", "tendertitle", "contracttitle", "label")
_URL_KEYS = ("url", "link", "href", "detailurl", "noticeurl", "permalink",
             "weburl", "documenturl")
_DATE_KEYS = ("date", "datepublished", "publisheddate", "publicationdate",
              "posteddate", "created", "startdate", "noticedate", "pubdate")
_CLOSE_KEYS = ("deadline", "closingdate", "closedate", "enddate", "expirydate",
               "duedate", "submissiondeadline", "responsedeadline", "validuntil")
_VALUE_KEYS = ("value", "amount", "estimatedvalue", "contractvalue", "budget",
               "price", "estimatedcost", "totalvalue")
_DESC_KEYS = ("description", "summary", "abstract", "details", "text", "body")
_REF_KEYS = ("id", "reference", "referencenumber", "noticeid", "noticenumber",
             "projectid", "tenderid", "solicitationnumber")


def _first_key(obj: dict, keys: tuple[str, ...]) -> str | None:
    lowered = {str(k).lower().replace("_", "").replace("-", ""): v
               for k, v in obj.items()}
    for key in keys:
        val = lowered.get(key)
        if isinstance(val, (str, int, float)) and clean(str(val)):
            return clean(str(val))
        if isinstance(val, dict):
            for sub in ("name", "value", "text", "@value", "amount"):
                if isinstance(val.get(sub), (str, int, float)):
                    return clean(str(val[sub]))
    return None


def _json_obj_to_row(obj: dict, base_url: str) -> Row | None:
    """Turn a JSON object into a Row, but only on corroborating evidence.

    A title alone is not enough -- an Organization node has a name and a url.
    Two further signals (a date, a value, a reference, a description or a
    deadline) are required before the object is believed to be a notice.
    """
    types = obj.get("@type") or obj.get("type") or ""
    if isinstance(types, list):
        types = " ".join(str(t) for t in types)
    if str(types).lower() in _SITE_TYPES:
        return None

    title = _first_key(obj, _TITLE_KEYS)
    if not title or _title_is_navish(title):
        return None

    url = _first_key(obj, _URL_KEYS)
    date_text = _first_key(obj, _DATE_KEYS)
    closing = _first_key(obj, _CLOSE_KEYS)
    value = _first_key(obj, _VALUE_KEYS)
    desc = _first_key(obj, _DESC_KEYS)
    ref = _first_key(obj, _REF_KEYS)

    corroborating = sum(1 for v in (date_text, closing, value, desc, ref) if v)
    if corroborating < 2:
        return None

    return Row(
        title=title,
        url=urljoin(base_url, url) if url else None,
        date_text=date_text,
        closing_text=closing,
        value_text=value,
        description=desc,
        reference=ref,
        raw_text=clean(json.dumps(obj, ensure_ascii=False))[:4000],
    )


def _walk_json(node, out: list[dict], depth: int = 0) -> None:
    if depth > 12 or len(out) > 5000:
        return
    if isinstance(node, dict):
        out.append(node)
        for v in node.values():
            _walk_json(v, out, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _walk_json(v, out, depth + 1)


def extract_embedded_json(html: str, base_url: str = "") -> LayerResult:
    """Pull notices out of JSON-LD, __NEXT_DATA__ or drupalSettings."""
    rows: list[Row] = []
    if not html:
        return LayerResult("embedded-json", rows, 0.0, "no html")

    soup = BeautifulSoup(html, "html.parser")
    blobs: list = []

    for tag in soup.find_all("script"):
        text = tag.string or tag.get_text() or ""
        text = text.strip()
        if not text:
            continue
        stype = (tag.get("type") or "").lower()
        tid = (tag.get("id") or "").lower()

        if "ld+json" in stype or tid == "__next_data__" or "json" in stype:
            try:
                blobs.append(json.loads(text))
            except (ValueError, TypeError):
                continue
        elif "drupalsettings" in text[:400] or "drupal-settings-json" in tid:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    blobs.append(json.loads(match.group()))
                except (ValueError, TypeError):
                    continue

    objects: list[dict] = []
    for blob in blobs:
        _walk_json(blob, objects)

    seen: set[tuple] = set()
    for obj in objects:
        row = _json_obj_to_row(obj, base_url)
        if row is None:
            continue
        key = (clean(row.title).lower(), row.url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    return LayerResult("embedded-json", rows, score_rows(rows))


# ---------------------------------------------------------------------------
# Layer 3 -- CSS selectors
# ---------------------------------------------------------------------------

# Field hints used when reading a selected node.
_DATE_HINT_ATTRS = ("datetime", "data-date", "data-published", "content")
_CLOSING_LABELS = ("deadline", "closing", "closes", "close date", "due",
                   "submission", "expiry", "expires", "frist", "abgabe",
                   "الموعد النهائي", "آخر موعد", "تاريخ الإغلاق")
_POSTED_LABELS = ("published", "posted", "date of publication", "release",
                  "veröffentlicht", "datum", "تاريخ النشر")
_VALUE_LABELS = ("value", "budget", "amount", "estimated", "contract value",
                 "wert", "القيمة", "قيمة العقد")


def _node_to_row(node, base_url: str) -> Row:
    text = clean(node.get_text(" "))

    link = node.find("a", href=True)
    url = urljoin(base_url, link["href"]) if link else None

    heading = node.find(["h1", "h2", "h3", "h4", "h5"])
    if heading and clean(heading.get_text()):
        title = clean(heading.get_text())
    elif link and clean(link.get_text()):
        title = clean(link.get_text())
    else:
        title = text[:160]

    row = Row(title=title, url=url, raw_text=text)

    # <time datetime="…"> and friends are unambiguous when present.
    for t in node.find_all(["time", "span", "div", "p", "td"]):
        for attr in _DATE_HINT_ATTRS:
            if t.has_attr(attr) and parse_date(t[attr]):
                row.date_text = row.date_text or clean(t[attr])
    if not row.date_text:
        time_tag = node.find("time")
        if time_tag:
            row.date_text = clean(time_tag.get_text())

    _assign_labelled_fields(row, text)
    return row


_DATE_SPAN_RE = re.compile(
    r"\d{4}-\d{1,2}-\d{1,2}"
    r"|\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{2,4}"
    r"|\d{1,2}\.?\s+[^\W\d_]{3,}(?:\s+[^\W\d_]{3,})?\s+\d{4}"
    r"|[^\W\d_]{3,}\s+\d{1,2},?\s+\d{4}",
    re.UNICODE,
)


def _first_date_text(tail: str) -> str | None:
    """The first date-shaped substring, so a label does not drag the whole row.

    Without this, "Deadline: 30 September 2026 Estimated value: EUR 1,850,000"
    is stored whole and the fuzzy date parser is left to guess which of the
    numbers is the deadline.
    """
    m = _DATE_SPAN_RE.search(tail)
    if m and parse_date(m.group()):
        return clean(m.group())
    return clean(tail) if parse_date(tail) else None


def _assign_labelled_fields(row: Row, text: str) -> None:
    """Read 'Deadline: 31.12.2026'-style labels out of a block of text."""
    low = text.lower()
    for label in _CLOSING_LABELS:
        idx = low.find(label)
        if idx != -1:
            found = _first_date_text(text[idx + len(label): idx + len(label) + 60])
            if found:
                row.closing_text = found
                break
    for label in _POSTED_LABELS:
        idx = low.find(label)
        if idx != -1:
            found = _first_date_text(text[idx + len(label): idx + len(label) + 60])
            if found:
                row.date_text = row.date_text or found
                break
    for label in _VALUE_LABELS:
        idx = low.find(label)
        if idx != -1:
            row.value_text = clean(text[idx: idx + 80])
            break
    if not row.value_text:
        row.value_text = text


def extract_by_selectors(html: str, selectors: list[str], base_url: str = "") -> LayerResult:
    """Try each selector in order; keep the best-scoring result.

    Every selector is scored rather than the first non-empty one being taken,
    because an over-broad selector matching the nav bar would otherwise win by
    arriving first.
    """
    if not html or not selectors:
        return LayerResult("selectors", [], 0.0, "no selectors configured")

    soup = BeautifulSoup(html, "html.parser")
    best = LayerResult("selectors", [], 0.0, "no selector matched")

    for selector in selectors:
        try:
            nodes = soup.select(selector)
        except Exception:
            continue
        if not nodes:
            continue
        rows = [_node_to_row(n, base_url) for n in nodes[:400]]
        rows = [r for r in rows if clean(r.title)]
        quality = score_rows(rows)
        if quality > best.quality:
            best = LayerResult("selectors", rows, quality, f"selector: {selector}")
    return best


# ---------------------------------------------------------------------------
# Layer 4 -- header-aware tables
# ---------------------------------------------------------------------------

_HEADER_MAP = {
    "title": _TITLE_KEYS + ("notice", "subject", "opportunity", "tender",
                            "description of assignment", "bezeichnung"),
    "closing": ("deadline", "closing date", "closes", "due date", "expiry",
                "submission deadline", "frist", "الموعد النهائي"),
    "posted": ("published", "posted", "publication date", "date published",
               "issue date", "veröffentlicht", "تاريخ النشر"),
    "value": ("value", "estimated value", "contract value", "budget", "amount",
              "wert", "القيمة"),
    "reference": ("reference", "ref", "notice id", "tender no", "number",
                  "reference number", "id"),
    "type": ("type", "notice type", "procurement type", "category"),
}


def _match_header(cell: str) -> str | None:
    c = clean(cell).lower().strip(" :*")
    if not c:
        return None
    for field_name, options in _HEADER_MAP.items():
        for opt in options:
            if c == opt or c.startswith(opt) or opt in c:
                return field_name
    return None


def extract_tables(html: str, base_url: str = "") -> LayerResult:
    """Map a table's header row onto fields, then read the body rows."""
    if not html:
        return LayerResult("table", [], 0.0, "no html")

    soup = BeautifulSoup(html, "html.parser")
    best = LayerResult("table", [], 0.0, "no table with a usable header")

    for table in soup.find_all("table"):
        header_cells = []
        head = table.find("thead")
        if head:
            tr = head.find("tr")
            if tr:
                header_cells = [clean(c.get_text()) for c in tr.find_all(["th", "td"])]
        if not header_cells:
            first = table.find("tr")
            if first:
                header_cells = [clean(c.get_text()) for c in first.find_all(["th", "td"])]

        mapping = {}
        for i, cell in enumerate(header_cells):
            fieldname = _match_header(cell)
            if fieldname and fieldname not in mapping.values():
                mapping[i] = fieldname
        if "title" not in mapping.values():
            continue

        body = table.find("tbody") or table
        trs = body.find_all("tr")
        rows: list[Row] = []
        for tr in trs:
            cells = tr.find_all(["td", "th"])
            if not cells or len(cells) < 2:
                continue
            texts = [clean(c.get_text(" ")) for c in cells]
            if texts == header_cells:
                continue
            row = Row(raw_text=" | ".join(texts))
            for i, fieldname in mapping.items():
                if i >= len(cells):
                    continue
                val = texts[i]
                if fieldname == "title":
                    row.title = val
                    link = cells[i].find("a", href=True)
                    if link:
                        row.url = urljoin(base_url, link["href"])
                elif fieldname == "closing":
                    row.closing_text = val
                elif fieldname == "posted":
                    row.date_text = val
                elif fieldname == "value":
                    row.value_text = val
                elif fieldname == "reference":
                    row.reference = val
                elif fieldname == "type":
                    row.extra["notice_type"] = val
            if not row.url:
                link = tr.find("a", href=True)
                if link:
                    row.url = urljoin(base_url, link["href"])
            if clean(row.title):
                rows.append(row)

        quality = score_rows(rows)
        if quality > best.quality:
            best = LayerResult("table", rows, quality,
                               f"header: {', '.join(header_cells[:6])}")
    return best


# ---------------------------------------------------------------------------
# Layer 5 -- structural inference (no class names at all)
# ---------------------------------------------------------------------------

_SKIP_CONTAINERS = {"nav", "header", "footer", "head", "script", "style",
                    "select", "aside", "form"}


def _signature(node) -> str:
    """Shape of a node, ignoring every class and id.

    Two sibling notice cards have the same tag and the same child tags even
    after a restyle, which is what makes this layer survive redesigns.
    """
    kids = sorted({c.name for c in node.find_all(True, recursive=False) if c.name})
    has_link = "yes" if node.find("a", href=True) else "no"
    return f"{node.name}|{','.join(kids)}|{has_link}"


def extract_structural(html: str, base_url: str = "") -> LayerResult:
    """Find the largest repeated sibling block and read it as a listing.

    NOTE: there is deliberately NO cap that rejects a container for having too
    many children. A previous build capped it and returned zero rows on a
    500-notice listing -- which is precisely the page this layer exists to
    rescue. Large containers are the good case, not the bad one.
    """
    if not html:
        return LayerResult("structural", [], 0.0, "no html")

    soup = BeautifulSoup(html, "html.parser")
    for junk in soup.find_all(list(_SKIP_CONTAINERS)):
        junk.decompose()

    best = LayerResult("structural", [], 0.0, "no repeated sibling block found")

    # Largest containers first. This is an ordering, NOT a filter -- every
    # container is still examined unless an unbeatable result is found. The
    # distinction matters: a previous build filtered here and returned zero
    # rows on a 500-notice page, which is the page this layer exists to save.
    containers = sorted(
        soup.find_all(True),
        key=lambda c: len(c.find_all(True, recursive=False)),
        reverse=True,
    )

    for container in containers:
        children = [c for c in container.find_all(True, recursive=False)
                    if c.name not in _SKIP_CONTAINERS]
        if len(children) < 3:
            continue

        # A near-perfect score on a substantial listing cannot be beaten, so
        # there is nothing left to find. This is a short-circuit on success,
        # never on size.
        if best.quality >= 0.95 and len(best.rows) >= 10:
            break

        groups: dict[str, list] = {}
        for child in children:
            groups.setdefault(_signature(child), []).append(child)

        for sig, members in groups.items():
            if len(members) < 3:
                continue
            rows = _drop_navish([_node_to_row(m, base_url) for m in members])
            if not rows:
                continue
            quality = score_rows(rows)
            if quality > best.quality:
                best = LayerResult(
                    "structural", rows, quality,
                    f"repeated <{container.name}> child block ({len(members)} rows, sig {sig})",
                )
    return best


# ---------------------------------------------------------------------------
# Layer 6 -- anchor URL pattern (last resort)
# ---------------------------------------------------------------------------

_DIGIT_RUN = re.compile(r"\d+")


def _nearest_row_text(anchor) -> str:
    """Text of the smallest ancestor that still looks like a single row.

    Walking straight to the first <div> ancestor is wrong twice over. On a
    flat listing that ancestor is the container holding every notice, so each
    row inherits the whole page's text -- which drags other rows' dates and
    values into this row's fields. It is also quadratic: get_text() over the
    full listing, once per link. Stopping at the nearest ancestor that holds
    just this one link fixes both.
    """
    node = anchor
    for _ in range(4):
        parent = node.parent
        if parent is None or parent.name in (None, "body", "html", "[document]"):
            break
        if _has_multiple_anchors(parent):
            break
        node = parent
    return clean(node.get_text(" "))[:1200]


def _has_multiple_anchors(node) -> bool:
    """Whether a node holds more than one link, exiting as soon as it knows.

    find_all() would walk the entire subtree, which on a listing container is
    the whole page -- once per link.
    """
    count = 0
    for descendant in node.descendants:
        if getattr(descendant, "name", None) == "a" and descendant.has_attr("href"):
            count += 1
            if count > 1:
                return True
    return False


def _href_shape(href: str) -> str:
    """Normalise a URL to its shape so sibling notice links group together."""
    href = href.split("#")[0]
    href = _DIGIT_RUN.sub("N", href)
    return re.sub(r"=[^&]+", "=V", href)


def extract_anchor_pattern(html: str, base_url: str = "",
                           hint: str | None = None) -> LayerResult:
    """Group links by URL shape and take the biggest plausible notice group."""
    if not html:
        return LayerResult("anchor-pattern", [], 0.0, "no html")

    soup = BeautifulSoup(html, "html.parser")
    for junk in soup.find_all(list(_SKIP_CONTAINERS)):
        junk.decompose()

    groups: dict[str, list] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        if hint and hint not in href:
            continue
        groups.setdefault(_href_shape(href), []).append(a)

    best = LayerResult("anchor-pattern", [], 0.0, "no repeated link pattern")
    for shape, anchors in groups.items():
        if len(anchors) < 3:
            continue
        rows = []
        for a in anchors:
            title = clean(a.get_text(" ")) or clean(a.get("title") or "")
            if not title or _title_is_navish(title):
                continue
            rows.append(Row(
                title=title,
                url=urljoin(base_url, a["href"]),
                raw_text=_nearest_row_text(a),
            ))
        for r in rows:
            _assign_labelled_fields(r, r.raw_text)
        rows = _drop_navish(rows)
        quality = score_rows(rows)
        if quality > best.quality:
            best = LayerResult("anchor-pattern", rows, quality, f"url shape: {shape}")
    return best


# ---------------------------------------------------------------------------
# The cascade
# ---------------------------------------------------------------------------

LAYER_ORDER = ["feed", "embedded-json", "selectors", "table", "structural",
               "anchor-pattern"]


def run_layers(content: str, base_url: str = "",
               selectors: list[str] | None = None,
               anchor_hint: str | None = None) -> list[LayerResult]:
    """Run every layer and return all results, best-effort, in cascade order."""
    results = [
        extract_feed(content, base_url),
        extract_embedded_json(content, base_url),
        extract_by_selectors(content, selectors or [], base_url),
        extract_tables(content, base_url),
        extract_structural(content, base_url),
        extract_anchor_pattern(content, base_url, anchor_hint),
    ]
    return results


def extract(content: str, base_url: str = "", selectors: list[str] | None = None,
            anchor_hint: str | None = None,
            threshold: float = QUALITY_THRESHOLD) -> LayerResult:
    """Run the cascade and return the first layer whose rows clear the gate.

    If none clears it, the best-scoring layer is returned with a note saying
    so, rather than nothing. A weak result the caller can see and diagnose is
    always better than a silent zero, which is indistinguishable from a quiet
    week.
    """
    # Lazily, in cascade order: a page whose feed or JSON layer already wins
    # should not pay for structural inference over the whole DOM. --capture
    # still calls run_layers() to report every layer's result.
    builders = [
        lambda: extract_feed(content, base_url),
        lambda: extract_embedded_json(content, base_url),
        lambda: extract_by_selectors(content, selectors or [], base_url),
        lambda: extract_tables(content, base_url),
        lambda: extract_structural(content, base_url),
        lambda: extract_anchor_pattern(content, base_url, anchor_hint),
    ]

    results: list[LayerResult] = []
    for build in builders:
        result = build()
        results.append(result)
        if result.rows and result.quality >= threshold:
            return result

    best = max(results, key=lambda r: (r.quality, len(r.rows)))
    if best.rows:
        best.note = (f"{best.note} | BELOW QUALITY GATE "
                     f"({best.quality:.2f} < {threshold:.2f}) - treat as unverified")
        return best

    empty = LayerResult("none", [], 0.0, diagnose(content, []))
    return empty
