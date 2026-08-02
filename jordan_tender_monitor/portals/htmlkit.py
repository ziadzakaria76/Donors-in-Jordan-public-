"""
Extraction primitives for the HTML-scraping portals.

The hard problem is that donor sites redesign without notice, so any scraper
pinned to CSS class names is one relaunch away from silently returning nothing.
This module therefore extracts through a cascade, most structured first:

  1. RSS/Atom feed         -- a published contract; survives redesigns entirely
  2. Embedded JSON         -- JSON-LD, __NEXT_DATA__, drupalSettings
  3. CSS selectors         -- fast and precise while the markup holds
  4. Header-aware tables   -- maps "Deadline"/"Published" columns to fields
  5. Structural inference  -- finds the repeated sibling block, ignoring classes
  6. Anchor pattern match  -- last resort

Layers 1, 2 and 5 are the ones that keep working after a redesign: none of them
depends on a class name.

`diagnose()` separates the two failure modes that need different fixes -- a bot
wall or JavaScript shell (install Playwright / the site is blocking us) from a
genuine layout change (update the selectors) -- so the report says something
actionable instead of "unavailable".
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urljoin, urlparse

import config

from .base import PortalError, clean_text, http_get, parse_date, soup_of

log = logging.getLogger(__name__)

MIN_TITLE_LENGTH = 12
MIN_GROUP_SIZE = 3
MAX_ELEMENTS_SCANNED = 30_000  # structural inference guard on very large pages

DATE_TEXT_RE = re.compile(
    r"\b(\d{1,2}[\s/.-][A-Za-z؀-ۿ]{3,14}[\s/.-]\d{4}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
    r"|[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}"
    r"|[٠-٩]{1,2}[\s/.-][؀-ۿ]{3,14}[\s/.-][٠-٩]{4})\b"
)

DEADLINE_LABELS = (
    "deadline", "closing", "closes", "submission", "expiry", "expires",
    "due", "response date", "last date", "bid closing", "offers by",
    "abgabefrist", "frist", "angebotsfrist", "date limite",
    "الموعد النهائي", "آخر موعد", "تاريخ الإغلاق", "اخر موعد",
)
POSTED_LABELS = (
    "published", "posted", "publication", "issued", "release date",
    "date of publication", "veröffentlicht", "veroeffentlicht",
    "date de publication", "تاريخ النشر", "نشر بتاريخ",
)

# Column-header -> canonical field, for table extraction
HEADER_FIELD_MAP = {
    "closing_date": ("deadline", "closing", "closes", "submission", "due",
                     "expiry", "abgabefrist", "frist", "date limite",
                     "الموعد النهائي", "تاريخ الإغلاق"),
    "posted_date": ("published", "posted", "publication", "issued", "date",
                    "veröffentlicht", "تاريخ النشر"),
    "estimated_value": ("value", "amount", "budget", "estimated", "contract value",
                        "wert", "montant", "القيمة"),
    "notice_type": ("type", "notice type", "procurement type", "category",
                    "art", "النوع"),
    "reference": ("reference", "ref", "reference no", "notice no", "id",
                  "referenz", "المرجع"),
    "country": ("country", "location", "place", "land", "pays", "الدولة"),
}

# Pages that loaded but are unusable, and why
_BOT_WALL_MARKERS = (
    "just a moment", "attention required", "cf-browser-verification",
    "captcha", "are you a robot", "access denied", "request unsuccessful",
    "incapsula incident", "ddos protection", "checking your browser",
)
_JS_REQUIRED_MARKERS = (
    "please enable javascript", "enable javascript to", "javascript is required",
    "you need to enable javascript", "<noscript>you need",
)


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------
def fetch_html(url: str, *, params: dict | None = None, js: bool = False) -> str:
    """Fetch a page as text, with encoding repaired and JS rendering optional."""
    if js:
        rendered = render_js(url)
        if rendered:
            return rendered
    resp = http_get(url, params=params)
    if resp.status_code >= 400:
        raise PortalError(f"HTTP {resp.status_code} from {url}")
    # requests guesses latin-1 for text/* without a charset, which mangles Arabic
    if not resp.encoding or resp.encoding.lower() in ("iso-8859-1", "ascii"):
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def render_js(url: str, wait_selector: str | None = None, timeout_ms: int = 30_000) -> str | None:
    """Render a JS-dependent page with headless Chromium. None if unavailable."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.info("Playwright not installed; using static HTML for %s", url)
        return None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=config.USER_AGENT)
                page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=timeout_ms // 2)
                    except Exception:
                        pass
                page.wait_for_timeout(2500)
                return page.content()
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 - a browser failure is never fatal
        log.warning("Playwright render failed for %s: %s", url, exc)
        return None


# --------------------------------------------------------------------------
# Diagnosis
# --------------------------------------------------------------------------
def diagnose(html: str) -> str | None:
    """Why is this page unusable? None means the page looks fine."""
    if not html or len(html) < 200:
        return "empty response"
    lowered = html.lower()
    for marker in _BOT_WALL_MARKERS:
        if marker in lowered:
            return (f"blocked by bot protection ({marker!r}) - the site is refusing "
                    "automated access; try running with Playwright installed or from "
                    "a different network")
    for marker in _JS_REQUIRED_MARKERS:
        if marker in lowered:
            return ("page requires JavaScript - run `playwright install chromium` "
                    "so this portal can be rendered")
    text = clean_text(soup_of(html).get_text(" "))
    if len(text) < 400 and lowered.count("<script") > 2:
        return ("page returned a JavaScript shell with no server-rendered content - "
                "run `playwright install chromium` so this portal can be rendered")
    return None


# --------------------------------------------------------------------------
# Layer 1: RSS / Atom
# --------------------------------------------------------------------------
def discover_feeds(html: str, base_url: str) -> list[str]:
    """Feed URLs advertised in <link rel="alternate">."""
    soup = soup_of(html)
    feeds = []
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel") or []).lower()
        ftype = (link.get("type") or "").lower()
        if "alternate" in rel and ("rss" in ftype or "atom" in ftype or "xml" in ftype):
            feeds.append(urljoin(base_url, link["href"]))
    return feeds


def _feed_tag(entry, names: tuple[str, ...]):
    """First child tag whose name matches, ignoring case and namespace prefix."""
    wanted = {n.lower() for n in names}
    for child in entry.find_all(True):
        if child.name.lower() in wanted:
            return child
    return None


def _feed_text(entry, names: tuple[str, ...]) -> str:
    tag = _feed_tag(entry, names)
    return clean_text(tag.get_text(" ")) if tag is not None else ""


def parse_feed(xml: str, base_url: str = "") -> list[dict]:
    """Rows from an RSS or Atom feed. Tag names are matched case-insensitively
    because XML parsing preserves case (<pubDate>, not <pubdate>)."""
    try:
        # Must parse as XML: the HTML parser treats <link> as a void element,
        # which silently empties every feed item's URL.
        soup = soup_of(xml, xml=True)
    except Exception:
        return []
    rows = []
    for entry in soup.find_all(lambda t: t.name.lower() in ("item", "entry")):
        title = _feed_text(entry, ("title",))
        if len(title) < MIN_TITLE_LENGTH:
            continue

        url = ""
        link_tag = _feed_tag(entry, ("link",))
        if link_tag is not None:
            url = clean_text(link_tag.get("href") or link_tag.get_text(" "))
        if not url:
            url = _feed_text(entry, ("guid", "id"))

        description = _feed_text(entry, ("description", "summary", "content"))
        published = _feed_text(entry, ("pubdate", "published", "updated", "date"))
        rows.append({
            "title": title,
            "url": urljoin(base_url, url) if url else base_url,
            "text": f"{title} | {description}",
            "fields": {"posted_date": published} if published else {},
            "source": "feed",
        })
    return rows


# --------------------------------------------------------------------------
# Layer 2: embedded JSON
# --------------------------------------------------------------------------
_TITLE_KEYS = ("title", "name", "headline", "noticetitle", "subject", "label")
_URL_KEYS = ("url", "link", "href", "permalink", "detailurl", "noticeurl")
_DEADLINE_KEYS = ("deadline", "closingdate", "closing_date", "enddate", "expirydate",
                  "submissiondeadline", "responsedeadline", "tenderdeadline")
_POSTED_KEYS = ("datepublished", "published", "posteddate", "publicationdate",
                "startdate", "created", "date")
_DESC_KEYS = ("description", "summary", "abstract", "body", "text", "content")
_VALUE_KEYS = ("value", "amount", "estimatedvalue", "budget", "contractvalue")

# schema.org types that describe the site rather than a notice
_NON_NOTICE_TYPES = {
    "Organization", "WebSite", "WebPage", "BreadcrumbList", "SearchAction",
    "ImageObject", "Person", "SiteNavigationElement", "LocalBusiness",
    "CollectionPage", "Corporation", "GovernmentOrganization", "Logo",
    "ContactPoint", "PostalAddress", "ListItem",
}


def _walk(node, depth: int = 0):
    """Yield every dict inside a nested JSON structure."""
    if depth > 12:
        return
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value, depth + 1)
    elif isinstance(node, list):
        for item in node[:400]:
            yield from _walk(item, depth + 1)


def _pick(obj: dict, keys: tuple[str, ...]) -> str:
    lowered = {k.lower().replace("-", "").replace("_", ""): v for k, v in obj.items()}
    for key in keys:
        value = lowered.get(key.replace("_", ""))
        if isinstance(value, (str, int, float)) and str(value).strip():
            return clean_text(value)
        if isinstance(value, dict):
            inner = _pick(value, ("value", "name", "url", "text", "en", "eng"))
            if inner:
                return inner
    return ""


def extract_embedded_json(html: str, base_url: str) -> list[dict]:
    """Rows from JSON-LD, __NEXT_DATA__ or other inline JSON blobs."""
    soup = soup_of(html)
    blobs: list = []

    for script in soup.find_all("script"):
        stype = (script.get("type") or "").lower()
        sid = (script.get("id") or "").lower()
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        if "ld+json" in stype or sid in ("__next_data__", "__nuxt_data__"):
            try:
                blobs.append(json.loads(raw))
            except (ValueError, TypeError):
                continue
        elif "json" in stype and len(raw) < 2_000_000:
            try:
                blobs.append(json.loads(raw))
            except (ValueError, TypeError):
                continue
        else:
            # drupalSettings / window.__INITIAL_STATE__ style assignments
            match = re.search(
                r"(?:drupalSettings|__INITIAL_STATE__|__PRELOADED_STATE__)\s*=\s*(\{.*?\});?\s*$",
                raw, re.DOTALL,
            )
            if match:
                try:
                    blobs.append(json.loads(match.group(1)))
                except (ValueError, TypeError):
                    continue

    rows, seen = [], set()
    for blob in blobs:
        for obj in _walk(blob):
            if str(obj.get("@type") or obj.get("type") or "") in _NON_NOTICE_TYPES:
                continue
            title = _pick(obj, _TITLE_KEYS)
            if len(title) < MIN_TITLE_LENGTH:
                continue
            url = _pick(obj, _URL_KEYS)
            fields = {}
            for field, keys in (("closing_date", _DEADLINE_KEYS),
                                ("posted_date", _POSTED_KEYS),
                                ("estimated_value", _VALUE_KEYS)):
                value = _pick(obj, keys)
                if value:
                    fields[field] = value
            description = _pick(obj, _DESC_KEYS)

            # Almost every real page embeds JSON-LD describing the site itself
            # ({"@type":"Organization","name":...,"url":...}). Accepting those
            # would hand the whole cascade a page full of phantom notices, so a
            # candidate must look like a record: a title plus at least two other
            # signals.
            signals = sum(bool(x) for x in (url, description, fields))
            if signals < 2:
                continue

            key = (title.lower(), url)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "title": title,
                "url": urljoin(base_url, url) if url else "",
                "text": f"{title} | {description}",
                "fields": fields,
                "source": "json",
            })
    return rows


# --------------------------------------------------------------------------
# Layer 3: CSS selectors
# --------------------------------------------------------------------------
def rows_from_selectors(html: str, base_url: str, selectors: list[str]) -> list[dict]:
    soup = soup_of(html)
    for selector in selectors:
        try:
            found = soup.select(selector)
        except Exception:
            continue
        rows = []
        for element in found:
            anchor = element.find("a", href=True)
            if not anchor:
                continue
            title = clean_text(anchor.get_text(" "))
            if len(title) < MIN_TITLE_LENGTH:
                title = clean_text(element.get_text(" "))[:200]
            if len(title) < MIN_TITLE_LENGTH:
                continue
            rows.append({
                "title": title,
                "url": urljoin(base_url, anchor["href"]),
                "text": clean_text(element.get_text(" | ")),
                "fields": {},
                "source": f"selector:{selector}",
            })
        if len(rows) >= 1:
            log.debug("selector %r matched %d rows", selector, len(rows))
            return rows
    return []


# --------------------------------------------------------------------------
# Layer 4: header-aware tables
# --------------------------------------------------------------------------
def _header_field(header: str) -> str | None:
    header = header.strip().lower()
    if not header:
        return None
    for field, aliases in HEADER_FIELD_MAP.items():
        if any(alias in header for alias in aliases):
            return field
    return None


def rows_from_tables(html: str, base_url: str) -> list[dict]:
    """Extract tabular listings, mapping column headers onto tender fields."""
    soup = soup_of(html)
    rows: list[dict] = []
    for table in soup.find_all("table"):
        header_cells = []
        head = table.find("thead")
        if head:
            header_cells = head.find_all(["th", "td"])
        if not header_cells:
            first = table.find("tr")
            if first:
                header_cells = first.find_all("th")
        headers = [clean_text(c.get_text(" ")) for c in header_cells]
        field_by_index = {i: _header_field(h) for i, h in enumerate(headers)}

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue
            anchor = tr.find("a", href=True)
            title = clean_text(anchor.get_text(" ")) if anchor else ""
            if len(title) < MIN_TITLE_LENGTH:
                longest = max((clean_text(c.get_text(" ")) for c in cells), key=len, default="")
                title = longest
            if len(title) < MIN_TITLE_LENGTH:
                continue
            fields = {}
            for idx, cell in enumerate(cells):
                field = field_by_index.get(idx)
                if field and field in ("closing_date", "posted_date",
                                       "estimated_value", "notice_type"):
                    value = clean_text(cell.get_text(" "))
                    if value:
                        fields[field] = value
            rows.append({
                "title": title,
                "url": urljoin(base_url, anchor["href"]) if anchor else base_url,
                "text": clean_text(tr.get_text(" | ")),
                "fields": fields,
                "source": "table",
            })
    return rows


# --------------------------------------------------------------------------
# Layer 5: structural inference (class-name independent)
# --------------------------------------------------------------------------
def _best_repeated_group(html: str) -> tuple[list, tuple | None]:
    """
    Largest set of sibling elements that share a tag/class signature and each
    contain one substantial link. Returns (members, signature).
    """
    soup = soup_of(html)
    best: list = []
    best_sig: tuple | None = None

    for index, parent in enumerate(soup.find_all(True)):
        if index > MAX_ELEMENTS_SCANNED:
            break
        children = [c for c in parent.find_all(recursive=False) if getattr(c, "name", None)]
        # No upper bound on children: a 500-row listing is precisely the case
        # this layer exists for. Total grouping work is already bounded by
        # MAX_ELEMENTS_SCANNED, since each element is a child exactly once.
        if len(children) < MIN_GROUP_SIZE:
            continue

        groups: dict = {}
        for child in children:
            classes = tuple(sorted(child.get("class") or []))[:2]
            groups.setdefault((child.name, classes), []).append(child)

        for signature, members in groups.items():
            if len(members) < MIN_GROUP_SIZE:
                continue
            usable = []
            for member in members:
                anchor = member.find("a", href=True)
                if anchor and len(clean_text(anchor.get_text(" "))) >= MIN_TITLE_LENGTH:
                    usable.append(member)
            if len(usable) >= MIN_GROUP_SIZE and len(usable) > len(best):
                best, best_sig = usable, signature

    return best, best_sig


def rows_from_structure(html: str, base_url: str) -> list[dict]:
    """
    Find the repeated sibling block that makes up a listing, without relying on
    any class name. This is what keeps working after a site redesign: a listing
    is almost always N sibling elements of the same tag, each containing one
    link with substantial text.
    """
    best, _ = _best_repeated_group(html)
    rows = []
    for element in best:
        anchor = element.find("a", href=True)
        rows.append({
            "title": clean_text(anchor.get_text(" ")),
            "url": urljoin(base_url, anchor["href"]),
            "text": clean_text(element.get_text(" | ")),
            "fields": {},
            "source": "structure",
        })
    if rows:
        log.debug("structural inference recovered %d rows", len(rows))
    return rows


def suggest_selectors(html: str) -> list[str]:
    """
    CSS selectors matching the listing this page actually uses.

    Used by `run.py --capture` so selector hints can be confirmed against a real
    page instead of guessed. Derived from the structurally-inferred listing
    block, so it works regardless of what the classes are called.
    """
    _, signature = _best_repeated_group(html)
    if not signature:
        return []
    tag, classes = signature
    out = []
    if classes:
        out.append(tag + "".join(f".{c}" for c in classes))
        out.append(f"{tag}[class*='{classes[0]}']")
    else:
        out.append(tag)
    return out


# --------------------------------------------------------------------------
# Layer 6: anchor pattern
# --------------------------------------------------------------------------
def rows_from_anchors(html: str, base_url: str, href_pattern: str) -> list[dict]:
    soup = soup_of(html)
    pattern = re.compile(href_pattern, re.IGNORECASE)
    rows, seen = [], set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not pattern.search(href):
            continue
        title = clean_text(anchor.get_text(" "))
        if len(title) < MIN_TITLE_LENGTH:
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        rows.append({
            "title": title,
            "url": url,
            "text": row_context(anchor),
            "fields": {},
            "source": "anchor",
        })
    return rows


# --------------------------------------------------------------------------
# The cascade
# --------------------------------------------------------------------------
QUALITY_THRESHOLD = 0.5


def listing_quality(rows: list[dict]) -> float:
    """
    How much does this row-set look like a real notice listing (0..1)?

    The selector hints in each portal module are unverified guesses, and a
    deliberately broad one -- bare `article`, `table tbody tr` -- will happily
    match navigation blocks, teasers or a "related documents" table. Selectors
    run before the class-independent layers, so without this gate one bad guess
    silently beats the layer that would have worked. Notice listings have
    distinguishing traits: many rows, distinct links, substantial titles, and
    dates somewhere in the row text.
    """
    if not rows:
        return 0.0
    count = len(rows)
    urls = [r.get("url") or "" for r in rows]
    titles = [r.get("title") or "" for r in rows]

    with_url = sum(1 for u in urls if u) / count
    unique_urls = len(set(u for u in urls if u)) / max(1, sum(1 for u in urls if u))
    unique_titles = len(set(titles)) / count
    with_date = sum(
        1 for r in rows
        if (r.get("fields") or {}).get("closing_date")
        or (r.get("fields") or {}).get("posted_date")
        or any_date(r.get("text") or "")
    ) / count
    median_title = sorted(len(t) for t in titles)[count // 2]

    # Dates dominate deliberately: carrying a published or closing date is the
    # single trait that separates a notice listing from navigation, teasers or
    # a related-documents table, all of which otherwise look similar.
    score = (
        0.40 * with_date
        + 0.20 * unique_urls              # nav menus repeat the same links
        + 0.15 * unique_titles
        + 0.10 * with_url
        + 0.10 * min(1.0, count / 3.0)    # a listing has several entries
        + 0.05 * min(1.0, median_title / 30.0)
    )
    return round(score, 3)


def extract_rows(
    html: str,
    base_url: str,
    *,
    selectors: list[str] | None = None,
    href_pattern: str | None = None,
) -> list[dict]:
    """
    Run the extraction layers in order and return the first whose rows look like
    a genuine listing. Layers that produce rows but fail the quality gate are
    kept as fallbacks; if no layer clears the bar, the best one is returned so a
    marginal page still yields something.
    """
    best_rows: list[dict] = []
    best_score = -1.0

    for label, extractor in (
        ("json", lambda: extract_embedded_json(html, base_url)),
        ("selectors", lambda: rows_from_selectors(html, base_url, selectors or [])),
        ("tables", lambda: rows_from_tables(html, base_url)),
        ("structure", lambda: rows_from_structure(html, base_url)),
        ("anchors", lambda: rows_from_anchors(html, base_url, href_pattern) if href_pattern else []),
    ):
        try:
            rows = extractor()
        except Exception as exc:  # noqa: BLE001 - a broken layer must not stop the rest
            log.debug("extraction layer %s failed: %s", label, exc)
            continue
        if not rows:
            continue
        score = listing_quality(rows)
        log.debug("layer %s produced %d rows, quality %.2f", label, len(rows), score)
        if score >= QUALITY_THRESHOLD:
            return rows
        if score > best_score:
            best_rows, best_score = rows, score

    if best_rows:
        log.debug("no layer cleared the quality gate; using best (%.2f)", best_score)
    return best_rows


def analyse_page(
    html: str,
    base_url: str,
    *,
    selectors: list[str] | None = None,
    href_pattern: str | None = None,
) -> dict:
    """
    Report how every layer performs on one real page.

    This is what `run.py --capture` uses to turn "the selectors are guesses"
    into a confirmed fact: run it against a live portal, see which layer wins
    and what selectors the page actually uses, then paste them into the module.
    """
    layers: dict[str, dict] = {}
    for label, extractor in (
        ("feed_links", lambda: [{"title": u, "url": u} for u in discover_feeds(html, base_url)]),
        ("json", lambda: extract_embedded_json(html, base_url)),
        ("selectors", lambda: rows_from_selectors(html, base_url, selectors or [])),
        ("tables", lambda: rows_from_tables(html, base_url)),
        ("structure", lambda: rows_from_structure(html, base_url)),
        ("anchors", lambda: rows_from_anchors(html, base_url, href_pattern) if href_pattern else []),
    ):
        try:
            rows = extractor()
        except Exception as exc:  # noqa: BLE001
            layers[label] = {"rows": 0, "quality": 0.0, "error": str(exc)[:120]}
            continue
        layers[label] = {
            "rows": len(rows),
            "quality": listing_quality(rows) if label != "feed_links" else 0.0,
            "sample": [r.get("title", "")[:80] for r in rows[:3]],
        }

    chosen = extract_rows(html, base_url, selectors=selectors, href_pattern=href_pattern)
    return {
        "diagnosis": diagnose(html),
        "layers": layers,
        "chosen_layer": chosen[0]["source"] if chosen else None,
        "chosen_rows": len(chosen),
        "suggested_selectors": suggest_selectors(html),
        "next_page": find_next_page(html, base_url),
    }


# --------------------------------------------------------------------------
# Pagination
# --------------------------------------------------------------------------
_NEXT_TEXTS = ("next", "next page", "weiter", "suivant", "التالي", "»", "›", ">")


def find_next_page(html: str, base_url: str) -> str | None:
    soup = soup_of(html)
    link = soup.find("link", rel="next", href=True)
    if link:
        return urljoin(base_url, link["href"])
    for anchor in soup.find_all("a", href=True):
        rel = " ".join(anchor.get("rel") or []).lower()
        label = clean_text(anchor.get_text(" ")).lower()
        aria = (anchor.get("aria-label") or "").lower()
        if rel == "next" or label in _NEXT_TEXTS or "next" in aria:
            candidate = urljoin(base_url, anchor["href"])
            if candidate != base_url:
                return candidate
    return None


# --------------------------------------------------------------------------
# Field helpers
# --------------------------------------------------------------------------
def row_context(element, levels: int = 3) -> str:
    """Text of the nearest enclosing row/card, used to find dates and values."""
    node = element
    for _ in range(levels):
        parent = getattr(node, "parent", None)
        if parent is None:
            break
        node = parent
        if getattr(node, "name", None) in ("tr", "li", "article", "section", "div"):
            text = clean_text(node.get_text(" "))
            if len(text) > 40:
                return text
    return clean_text(getattr(element, "get_text", lambda *_: "")(" "))


def labelled_date(text: str, labels: tuple[str, ...]) -> str | None:
    """Find a date appearing shortly after one of `labels`."""
    if not text:
        return None
    lowered = text.lower()
    for label in labels:
        idx = lowered.find(label)
        if idx == -1:
            continue
        match = DATE_TEXT_RE.search(text[idx: idx + 200])
        if match:
            return match.group(1)
    return None


def any_date(text: str) -> str | None:
    match = DATE_TEXT_RE.search(text or "")
    return match.group(1) if match else None


def resolve_dates(row: dict) -> tuple[str | None, str | None]:
    """(posted, closing) from a row's structured fields, then its free text."""
    fields = row.get("fields") or {}
    text = row.get("text") or ""
    posted = fields.get("posted_date") or labelled_date(text, POSTED_LABELS)
    closing = fields.get("closing_date") or labelled_date(text, DEADLINE_LABELS)
    if not closing and not posted:
        # A single unlabelled date on a tender listing is far more often the
        # deadline than the posting date.
        closing = any_date(text)
    return posted, closing


def enrich_from_detail(row: dict, budget: list[int]) -> None:
    """
    Fetch a notice's own page to recover a missing deadline or value.

    Listing pages frequently omit both. `budget` is a single-element list acting
    as a shared counter so a portal cannot spend more than its allowance of
    extra requests.
    """
    if budget[0] <= 0 or not row.get("url"):
        return
    if (row.get("fields") or {}).get("closing_date"):
        return
    try:
        html = fetch_html(row["url"])
    except Exception:  # noqa: BLE001 - enrichment is strictly best-effort
        return
    budget[0] -= 1
    text = clean_text(soup_of(html).get_text(" "))
    fields = row.setdefault("fields", {})
    for field, labels in (("closing_date", DEADLINE_LABELS), ("posted_date", POSTED_LABELS)):
        if not fields.get(field):
            found = labelled_date(text, labels)
            if found:
                fields[field] = found
    row["text"] = f"{row.get('text', '')} | {text[:1500]}"



def same_host(url: str, base_url: str) -> bool:
    try:
        return urlparse(url).netloc.lower() == urlparse(base_url).netloc.lower()
    except ValueError:
        return False


__all__ = [
    "DEADLINE_LABELS", "POSTED_LABELS", "any_date", "diagnose", "discover_feeds",
    "enrich_from_detail", "extract_embedded_json", "extract_rows", "fetch_html",
    "find_next_page", "labelled_date", "parse_date", "parse_feed", "render_js",
    "resolve_dates", "row_context", "rows_from_anchors",
    "rows_from_selectors", "rows_from_structure", "rows_from_tables", "same_host",
]
