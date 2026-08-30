"""Class-independent extraction cascade.

Donor sites redesign without notice, and a scraper pinned to CSS class names is
one relaunch away from silently returning nothing. Six layers are tried in
order; layers 1, 2 and 5 use no class names at all:

    1. RSS/Atom feed      -- a published contract, survives redesigns
    2. Embedded JSON      -- JSON-LD, __NEXT_DATA__, drupalSettings
    3. CSS selectors      -- fast while the markup holds
    4. Header-aware table -- map Deadline/Published/Value columns to fields
    5. Structural         -- the repeated sibling block, ignoring classes
    6. Anchor URL pattern -- last resort

Selectors run BEFORE the class-independent layers, so an over-broad guess like
a bare `article` or `table tbody tr` would match navigation or a
related-documents table and short-circuit the layer that would have worked.
Every layer is therefore scored for listing-likeness and must clear a threshold
to win; carrying a date is weighted most heavily, because that is what
separates a notice listing from a nav menu. If no layer clears the bar, the
best one is returned rather than nothing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .dates import _DATE_SHAPED

QUALITY_THRESHOLD = 0.45

# schema.org types that describe the site rather than a notice. Nearly every
# page embeds {"@type":"Organization","name":...,"url":...}; accepting it fills
# the report with phantom notices.
SITE_TYPES = {"organization", "website", "webpage", "breadcrumblist", "sitenavigationelement",
              "collectionpage", "searchresultspage", "imageobject", "logo", "person"}

TITLE_KEYS = ("title", "name", "headline", "subject", "noticetitle", "label")
URL_KEYS = ("url", "link", "href", "permalink", "detailurl")
DATE_KEYS = ("date", "deadline", "closing", "published", "posted", "pubdate", "expiry", "created")


@dataclass
class Row:
    title: str = ""
    url: Optional[str] = None
    text: str = ""
    cells: dict = field(default_factory=dict)
    raw: Any = None

    @property
    def has_date(self) -> bool:
        blob = " ".join([self.text] + [str(v) for v in self.cells.values()])
        return bool(_DATE_SHAPED.search(blob))


@dataclass
class LayerResult:
    layer: str
    rows: list[Row]
    quality: float = 0.0
    note: str = ""

    @property
    def wins(self) -> bool:
        return bool(self.rows) and self.quality >= QUALITY_THRESHOLD


@dataclass
class ExtractionResult:
    rows: list[Row]
    layer: str
    quality: float
    attempts: list[LayerResult]
    diagnosis: Optional[str] = None


# --------------------------------------------------------------------- quality
def score_rows(rows: list[Row]) -> float:
    """How much does this look like a genuine listing rather than a nav menu?"""
    if not rows:
        return 0.0
    n = len(rows)
    with_date = sum(1 for r in rows if r.has_date) / n
    with_title = sum(1 for r in rows if 12 <= len(r.title.strip()) <= 300) / n
    with_url = sum(1 for r in rows if r.url) / n
    enough = min(n, 3) / 3

    # Distinct titles: a nav menu repeats itself across rows.
    distinct = len({r.title.strip().lower() for r in rows if r.title.strip()}) / n if n else 0

    score = (0.45 * with_date) + (0.20 * with_title) + (0.15 * with_url) \
            + (0.10 * enough) + (0.10 * distinct)
    return round(score, 4)


def _finish(layer: str, rows: list[Row], note: str = "") -> LayerResult:
    rows = [r for r in rows if (r.title or "").strip()]
    return LayerResult(layer=layer, rows=rows, quality=score_rows(rows), note=note)


# ---------------------------------------------------------------- layer 1: feed
def feed_layer(text: str, base_url: str = "") -> LayerResult:
    """RSS/Atom.

    Parsed as XML, never HTML: BeautifulSoup's HTML parser treats <link> as a
    void element, so the feed's links come back empty. Tag names are matched
    case-insensitively because <pubDate> will not match a search for "pubdate".
    """
    if "<rss" not in text[:2000].lower() and "<feed" not in text[:2000].lower():
        return LayerResult("feed", [], note="not a feed")
    soup = BeautifulSoup(text, "xml")
    rows: list[Row] = []
    for item in soup.find_all(re.compile(r"^(item|entry)$", re.I)):
        title_el = item.find(re.compile(r"^title$", re.I))
        link_el = item.find(re.compile(r"^link$", re.I))
        url = None
        if link_el is not None:
            url = (link_el.get("href") or link_el.get_text(strip=True) or "").strip() or None
        date_el = item.find(re.compile(r"^(pubDate|published|updated|date)$", re.I))
        cells = {}
        if date_el is not None:
            cells["date"] = date_el.get_text(strip=True)
        desc = item.find(re.compile(r"^(description|summary|content)$", re.I))
        rows.append(Row(
            title=title_el.get_text(strip=True) if title_el else "",
            url=urljoin(base_url, url) if url else None,
            text=desc.get_text(" ", strip=True) if desc else "",
            cells=cells, raw=str(item)[:2000],
        ))
    return _finish("feed", rows)


# --------------------------------------------------------- layer 2: embedded JSON
def _looks_like_notice(obj: dict) -> bool:
    """Require a title plus two corroborating signals.

    Without this, the site-level JSON-LD blob every page carries becomes a row.
    """
    keys = {k.lower() for k in obj.keys()}
    obj_type = str(obj.get("@type") or obj.get("type") or "").lower()
    if obj_type in SITE_TYPES:
        return False
    has_title = any(any(t == k or t in k for t in TITLE_KEYS) for k in keys)
    if not has_title:
        return False
    corroborating = 0
    if any(any(u == k or u in k for u in URL_KEYS) for k in keys):
        corroborating += 1
    if any(any(d in k for d in DATE_KEYS) for k in keys):
        corroborating += 1
    if len(keys) >= 5:
        corroborating += 1
    return corroborating >= 2


def _walk_json(node: Any, out: list[dict], depth: int = 0) -> None:
    if depth > 12:
        return
    if isinstance(node, dict):
        if _looks_like_notice(node):
            out.append(node)
        for value in node.values():
            _walk_json(value, out, depth + 1)
    elif isinstance(node, list):
        for value in node:
            _walk_json(value, out, depth + 1)


def _first(obj: dict, keys: Iterable[str]) -> Optional[str]:
    for k, v in obj.items():
        kl = k.lower()
        if any(t == kl or t in kl for t in keys):
            if isinstance(v, (str, int, float)) and str(v).strip():
                return str(v).strip()
            if isinstance(v, dict):
                for sub in v.values():
                    if isinstance(sub, str) and sub.strip():
                        return sub.strip()
    return None


def embedded_json_layer(soup: BeautifulSoup, base_url: str = "") -> LayerResult:
    found: list[dict] = []
    for script in soup.find_all("script"):
        payload = script.string or script.get_text() or ""
        payload = payload.strip()
        if not payload:
            continue
        script_type = (script.get("type") or "").lower()
        ident = (script.get("id") or "").lower()
        if not (script_type == "application/ld+json" or ident == "__next_data__"
                or "drupalsettings" in payload[:200].lower() or payload.startswith(("{", "["))):
            continue
        if payload.startswith("window."):
            payload = payload.split("=", 1)[-1].strip().rstrip(";")
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            continue
        _walk_json(data, found)

    rows = []
    for obj in found:
        url = _first(obj, URL_KEYS)
        rows.append(Row(
            title=_first(obj, TITLE_KEYS) or "",
            url=urljoin(base_url, url) if url else None,
            text=" ".join(str(v) for v in obj.values() if isinstance(v, (str, int, float)))[:1500],
            cells={k: v for k, v in obj.items() if isinstance(v, (str, int, float))},
            raw=obj,
        ))
    return _finish("embedded_json", rows)


# ------------------------------------------------------------ layer 3: selectors
def selector_layer(soup: BeautifulSoup, selectors: Optional[dict], base_url: str = "") -> LayerResult:
    if not selectors or not selectors.get("row"):
        return LayerResult("selectors", [], note="no selectors configured")
    rows = []
    for node in soup.select(selectors["row"]):
        title_node = node.select_one(selectors["title"]) if selectors.get("title") else node
        # The link must go somewhere. This took `node.find("a")` unconditionally,
        # so a row whose first anchor is a button wired href="#" -- UNGM renders
        # two such save controls per row -- produced a URL that resolves to the
        # listing page with a fragment. The other layers already refuse those;
        # this one emitted them, and a dead link in a report satisfies neither
        # the reader nor the Word writer's promise of a link or a stated reason.
        configured = selectors.get("link")
        candidates = node.select(configured) if configured else node.find_all("a")
        link_node = next((a for a in candidates if _is_navigable(a.get("href"))), None)
        href = link_node.get("href") if link_node else None
        cells = {}
        for key in ("deadline", "published", "value", "buyer", "type"):
            sel = selectors.get(key)
            if sel:
                el = node.select_one(sel)
                if el:
                    cells[key] = el.get_text(" ", strip=True)
        rows.append(Row(
            title=title_node.get_text(" ", strip=True) if title_node else "",
            url=urljoin(base_url, href) if href else None,
            text=node.get_text(" ", strip=True)[:2000],
            cells=cells, raw=str(node)[:2000],
        ))
    return _finish("selectors", rows)


# --------------------------------------------------------- layer 4: header table
HEADER_MAP = {
    "deadline": ("deadline", "closing", "closes", "expiry", "abgabefrist", "frist", "clôture",
                 "الموعد النهائي", "آخر موعد", "تاريخ الإغلاق"),
    "published": ("published", "posted", "date", "veröffentlicht", "publication",
                  "تاريخ النشر"),
    "value": ("value", "amount", "budget", "estimated", "wert", "القيمة"),
    "buyer": ("buyer", "agency", "organisation", "organization", "entity", "auftraggeber", "office",
              "الجهة"),
    "type": ("type", "notice type", "category", "art", "النوع"),
    "title": ("title", "subject", "description", "bezeichnung", "gegenstand", "objet",
              "العنوان", "الموضوع"),
    "reference": ("reference", "ref", "number", "no.", "nummer", "الرقم"),
}


def cell_text(cell) -> str:
    """Take a cell's OWN text, not the text of cells nested inside it.

    One unclosed <td> is enough to ruin an otherwise perfect table: with
    `<td>03.08.2026</td><td>n.v.<td>10030355 - Studie ...</td>` the parser nests
    the title, type and buyer inside the unclosed cell. find_all() still returns
    the right number of cells in the right order and the header still maps
    correctly -- the row simply comes out with a closing date containing the
    title and the buyer.

    Restricting find_all to direct children is NOT the fix: on that markup it
    returns two cells instead of six and the column indices collapse.
    """
    parts = []
    for string in cell.find_all(string=True):
        nearest = string.find_parent(["td", "th"])
        if nearest is cell:
            text = string.strip()
            if text:
                parts.append(text)
    return " ".join(parts)


def _map_headers(header_cells: list[str]) -> dict[int, str]:
    mapping = {}
    for idx, raw in enumerate(header_cells):
        low = raw.strip().lower()
        for field_name, needles in HEADER_MAP.items():
            if any(n in low for n in needles):
                mapping.setdefault(idx, field_name)
                break
    return mapping


def table_layer(soup: BeautifulSoup, base_url: str = "") -> LayerResult:
    best: Optional[LayerResult] = None
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if not header_row:
            continue
        header_cells = [cell_text(c) for c in header_row.find_all(["th", "td"])]
        mapping = _map_headers(header_cells)
        if not mapping:
            continue
        rows = []
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            values = {}
            for idx, cell in enumerate(cells):
                name = mapping.get(idx, f"col{idx}")
                values[name] = cell_text(cell)
            link = tr.find("a")
            href = link.get("href") if link else None
            rows.append(Row(
                title=values.get("title") or (link.get_text(" ", strip=True) if link else "")
                      or values.get("reference", ""),
                url=urljoin(base_url, href) if href else None,
                text=" | ".join(f"{k}: {v}" for k, v in values.items() if v),
                cells=values, raw=str(tr)[:2000],
            ))
        result = _finish("table", rows)
        if best is None or result.quality > best.quality:
            best = result
    return best or LayerResult("table", [], note="no header table found")


# ------------------------------------------------- layer 4b: repeated class
def _class_signature(el) -> Optional[str]:
    classes = el.get("class") or []
    return f"{el.name}.{'.'.join(sorted(classes))}" if classes else None


def repeated_class_layer(soup: BeautifulSoup, base_url: str = "") -> LayerResult:
    """Rows that share a class, wherever they sit in the tree.

    WHY THIS EXISTS. `structural_layer` groups DIRECT SIBLINGS. On UNGM the
    notice rows are not siblings of one another -- the live capture found
    fifteen `div.tableRow` in the markup and no structural candidate above six,
    every one of them `div>span`, which is the cells inside a single row
    matched as though they were the listing. The rows were never considered.
    Nothing about a better title or URL could help, because no row was ever a
    candidate.

    A page that repeats a class fifteen times is telling you what its rows are.
    That is evidence the page volunteers, unlike a hand-written selector, which
    is why this does not conflict with the project's refusal to ship guessed
    CSS: nothing here is configured per portal, it is all discovered.

    ORDERED BEFORE structural, and that placement is the whole risk. The
    cascade returns the FIRST layer over the quality bar rather than the best,
    so a layer added after structural would never run on this page -- structural
    already "wins" with its wrong 0.56. Going first means this layer now
    decides pages that structural used to decide, which is what the committed
    fixtures exist to police.

    The nav menu is the failure this must not cause. A navigation list repeats
    its class more consistently than any listing does, so class repetition
    ALONE would hand the page to the navigation -- exactly what
    `structural_layer` warns about. The quality gate is what separates them: nav
    items carry no dates and repeat their titles, so they score far below the
    bar and lose to a later layer or to nothing at all.
    """
    groups: dict[str, list] = {}
    for element in soup.find_all(True):
        signature = _class_signature(element)
        if signature:
            groups.setdefault(signature, []).append(element)

    best = LayerResult("repeated_class", [], note="no class repeated three times")
    seen: list[tuple[int, int, float, str]] = []
    for signature, group in groups.items():
        if len(group) < 3:
            continue
        # Drop groups whose members nest inside one another. A wrapper class
        # used at two depths would otherwise count the same notice twice, and
        # the duplicate rows would look like a fuller listing rather than a
        # double count.
        outermost = [el for el in group
                     if not any(other is not el and other in el.parents for other in group)]
        if len(outermost) < 3:
            continue
        candidate = _finish("repeated_class", _rows_from_group(outermost, base_url))
        seen.append((len(outermost), len(candidate.rows), candidate.quality, signature))
        if (candidate.quality, len(candidate.rows)) > (best.quality, len(best.rows)):
            best = candidate

    if seen:
        seen.sort(key=lambda c: (-c[2], -c[0]))
        best.note = ("candidates (group->rows kept, quality, class): "
                     + "; ".join(f"{size}->{kept} q={q:.2f} {sig}"
                                 for size, kept, q, sig in seen[:6]))
    return best


# ---------------------------------------------------------- layer 5: structural
def _signature(el) -> str:
    """Shape of a node, ignoring class names entirely."""
    return el.name + ">" + ",".join(sorted({c.name for c in el.find_all(recursive=False)}))


def _is_navigable(href: Optional[str]) -> bool:
    """Does this href go anywhere a reader could follow?

    "#" and javascript: are how a page wires a button that is not a link. A
    report that renders one as the notice's URL sends the reader nowhere and
    says nothing about it, which is worse than admitting there is no link.
    """
    if not href:
        return False
    target = href.strip().lower()
    return bool(target) and not target.startswith(("#", "javascript:"))


def _rows_from_group(group: list, base_url: str) -> list[Row]:
    """Turn a group of sibling nodes into rows.

    THE FIRST ANCHOR IS NOT THE TITLE. It was taken as both title and URL, and
    on UNGM that is an icon-only "save this notice" button rendered before the
    notice link -- so every row came back with an empty title and href="#".
    Empty titles are then dropped by `_finish`, which wiped the entire group and
    let a group of table *cells* win instead: fifteen notices became four rows
    whose titles were "30-Sep-2026", "29-Jul-2026" and "UNDP".

    That is the worst shape this failure could take. It is not an empty result
    anyone would question -- it is a plausible-looking listing of the wrong
    thing, and the row count is the only hint.

    NOR IS IT THE FIRST ANCHOR WITH TEXT. That was the first correction and it
    was still wrong, because it assumed the save button is an icon with no text.
    UNGM's is an icon with an accessible label -- "Unsave this procurement
    opportunity. Subscribe to UNGM Pro ..." -- so it satisfies "has text" and
    won the title anyway. Confirmed live: every UNGM notice in the run of
    2026-08-30 was titled "Unsave this procurement opportunity." The fixture
    that vetted the first correction rendered that button as
    `<a href="#"><svg></svg></a>`, textless, which is the one shape where the
    bug does not reproduce -- so the test passed and the page stayed broken.

    So the rule is a conjunction, not two independent lookups: prefer the
    anchor that BOTH goes somewhere AND says something, which is what a title
    link is. A button wired with href="#" is excluded by the first half however
    much text it carries, and a bare icon link by the second.

    The split lookup remains as the fallback, because a row whose link is an
    icon and whose title is plain text is a real arrangement -- it is just not
    the common one, and it must not be what decides the common one.
    """
    rows = []
    for node in group:
        anchors = node.find_all("a")
        # A title link goes somewhere and says something. Look for that first.
        primary = next((a for a in anchors
                        if _is_navigable(a.get("href")) and a.get_text(" ", strip=True)), None)
        titled = primary or next((a for a in anchors if a.get_text(" ", strip=True)), None)
        linked = primary or next((a for a in anchors if _is_navigable(a.get("href"))), None)

        text = node.get_text(" ", strip=True)
        # Fall back to the node's own text, as before, when no anchor carries
        # any: a listing whose rows are not links is still a listing.
        title = titled.get_text(" ", strip=True) if titled else text[:120]
        href = linked.get("href") if linked else None

        rows.append(Row(title=title, url=urljoin(base_url, href) if href else None,
                        text=text[:2000], raw=str(node)[:2000]))
    return rows


def structural_layer(soup: BeautifulSoup, base_url: str = "") -> LayerResult:
    """Find the repeated sibling block, ignoring classes.

    Candidate groups are chosen by listing-likeness, not by size: a three-item
    nav menu and a three-item notice list are the same shape, and picking the
    first or largest group hands the page to the navigation. Scoring every
    candidate costs O(nodes) overall, because each element belongs to exactly
    one sibling group under its own parent.

    Deliberately has NO "container too large" guard. A cap like that silently
    returns zero rows on a 500-notice listing -- exactly the page this layer
    exists to rescue. Sizes 50, 500 and 2000 are all in the test suite.
    """
    best = LayerResult("structural", [], note="no repeated sibling block found")
    # Every candidate considered, so a losing group can be seen losing. Which
    # group wins is the whole behaviour of this layer, and until now the only
    # output was the winner -- leaving "why did it read 6 of 15 rows" to be
    # answered by guessing at markup nobody can fetch.
    seen: list[tuple[int, int, float, str]] = []

    for container in soup.find_all(True):
        children = [c for c in container.find_all(recursive=False)
                    if c.name not in ("script", "style")]
        if len(children) < 3:
            continue
        groups: dict[str, list] = {}
        for child in children:
            groups.setdefault(_signature(child), []).append(child)
        for signature, group in groups.items():
            if len(group) < 3:
                continue
            candidate = _finish("structural", _rows_from_group(group, base_url))
            # Group size AND surviving rows: they differ exactly when _finish
            # drops rows for having no title, which is a failure mode that
            # otherwise leaves no trace.
            seen.append((len(group), len(candidate.rows), candidate.quality, signature))
            if (candidate.quality, len(candidate.rows)) > (best.quality, len(best.rows)):
                best = candidate

    if seen:
        # Biggest first: the question is always "why did the large group lose".
        seen.sort(key=lambda c: (-c[0], -c[2]))
        parts = [f"{size}->{kept} q={quality:.2f} {signature}"
                 for size, kept, quality, signature in seen[:6]]
        best.note = ("candidates (group->rows kept, quality, shape): "
                     + "; ".join(parts))
    return best


# -------------------------------------------------------------- layer 6: anchors
def anchor_layer(soup: BeautifulSoup, pattern: Optional[str], base_url: str = "") -> LayerResult:
    if not pattern:
        return LayerResult("anchors", [], note="no anchor pattern configured")
    rx = re.compile(pattern, re.IGNORECASE)
    rows = []
    seen = set()
    for a in soup.find_all("a", href=True):
        if not rx.search(a["href"]) or a["href"] in seen:
            continue
        seen.add(a["href"])
        parent = a.find_parent(["tr", "li", "div", "article"]) or a
        rows.append(Row(title=a.get_text(" ", strip=True),
                        url=urljoin(base_url, a["href"]),
                        text=parent.get_text(" ", strip=True)[:2000],
                        raw=str(parent)[:2000]))
    return _finish("anchors", rows)


# ------------------------------------------------------------------- diagnosis
def diagnose(html: str, status: int = 200) -> Optional[str]:
    """Name the failure, because each one needs a different fix."""
    low = (html or "").lower()
    if status in (403, 429) or any(s in low for s in
                                   ("cloudflare", "cf-browser-verification", "incapsula",
                                    "just a moment", "attention required", "access denied",
                                    "enable javascript and cookies")):
        return "bot_wall: use a different network or drive it with Playwright"
    # Strip script and style BODIES before counting visible words. Stripping
    # only the tags leaves the JavaScript source itself in the count, so a page
    # whose entire listing is built by a sizeable bootstrap script -- the exact
    # shape this check exists to catch -- looks text-rich and is misdiagnosed as
    # a layout change, which never escalates to a browser.
    stripped = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", low, flags=re.S)
    body_text = re.sub(r"<[^>]+>", " ", stripped)
    if len(body_text.split()) < 60 and ("<script" in low or "__next_data__" in low
                                        or "app-root" in low or "id=\"app\"" in low
                                        or "id=\"root\"" in low):
        return "js_shell: page renders client-side -- playwright install chromium"
    if status >= 500 or status == 404:
        return f"transport: HTTP {status} -- wrong URL or blocked host"
    return "layout_change: page fetched fine but no layer found a listing"


# --------------------------------------------------------------------- cascade
def extract(html: str, base_url: str = "", selectors: Optional[dict] = None,
            anchor_pattern: Optional[str] = None, status: int = 200) -> ExtractionResult:
    attempts: list[LayerResult] = []

    feed = feed_layer(html, base_url)
    attempts.append(feed)
    if feed.wins:
        return ExtractionResult(feed.rows, feed.layer, feed.quality, attempts)

    soup = BeautifulSoup(html, "html.parser")
    for layer in (embedded_json_layer(soup, base_url),
                  selector_layer(soup, selectors, base_url),
                  table_layer(soup, base_url),
                  repeated_class_layer(soup, base_url),
                  structural_layer(soup, base_url),
                  anchor_layer(soup, anchor_pattern, base_url)):
        attempts.append(layer)
        if layer.wins:
            return ExtractionResult(layer.rows, layer.layer, layer.quality, attempts)

    # Nothing cleared the bar: return the best attempt rather than nothing.
    best = max(attempts, key=lambda a: (a.quality, len(a.rows)))
    return ExtractionResult(best.rows, best.layer, best.quality, attempts,
                            diagnosis=diagnose(html, status) if not best.rows else
                            "below_quality_threshold: returning best-effort rows")
