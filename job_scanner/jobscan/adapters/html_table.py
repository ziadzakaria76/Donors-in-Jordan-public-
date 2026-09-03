"""Server-rendered results tables.

Not every careers page is an XHR app. Where the vacancy list arrives inside the
HTML document -- as JHAH's results tables are expected to -- this adapter reads
it directly, and no browser is needed at any point in the weekly run.

Rows are located by CSS selector, so a discovered layout is expressed in
config rather than in code. Where a source supplies no selectors, the adapter
tries a small set of conventional table shapes and reports which one worked,
so the guess can be pinned down in sources.yaml afterwards.
"""

from __future__ import annotations

from typing import Any, Callable

from bs4 import BeautifulSoup

from ..model import Posting
from ..normalize import parse_date
from . import AdapterError

# Tried in order when a source has no explicit row_selector. Each is a real
# markup convention, not a wildcard: a wrong guess must fail visibly.
FALLBACK_ROW_SELECTORS = (
    "table.jobs tbody tr",
    "table tbody tr",
    "ul.job-list li",
    "div.job-listing",
    "article.job",
)

HEADER_HINTS = {
    "title": ("title", "position", "job", "vacancy", "role", "designation"),
    "location": ("location", "city", "site", "region", "place"),
    "department": ("department", "division", "specialty", "speciality", "unit", "category"),
    "posted_at": ("posted", "published", "date posted", "posting date"),
    "closing_at": ("closing", "deadline", "expires", "last date", "close"),
}


def _text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _cell(row, selector: str | None):
    if not selector:
        return None
    try:
        return row.select_one(selector)
    except Exception:  # an invalid selector is a config error, not a crash
        return None


def _header_map(soup, row_selector: str) -> dict[str, int]:
    """Infer column positions from a table's header row.

    Column order differs between employers, so reading the header is more
    durable than hard-coding nth-child positions -- and it is what lets the
    fallback path produce something usable at all.
    """
    table = soup.select_one(row_selector.split(" tbody")[0]) if "tbody" in row_selector else None
    headers = []
    if table:
        headers = [_text(th).lower() for th in table.select("thead th, thead td, tr:first-child th")]
    if not headers:
        return {}
    mapping: dict[str, int] = {}
    for field, hints in HEADER_HINTS.items():
        for index, header in enumerate(headers):
            if any(hint in header for hint in hints):
                mapping.setdefault(field, index)
                break
    return mapping


def fetch(source: dict[str, Any], fetcher, note: Callable[[str], None]) -> list[Posting]:
    spec = source.get("html") or {}
    url = spec.get("url") or source.get("careers_url")
    if not url:
        raise AdapterError(f"{source['key']}: no html.url or careers_url configured")

    response = fetcher.get(url)
    if not response.ok:
        detail = response.error
        if response.text:
            detail += f" | body starts: {response.text[:300]}"
        raise AdapterError(f"{source['key']}: {detail}")

    soup = BeautifulSoup(response.text, "lxml")

    row_selector = spec.get("row_selector")
    rows: list = []
    if row_selector:
        rows = soup.select(row_selector)
        if not rows:
            raise AdapterError(
                f"{source['key']}: row_selector {row_selector!r} matched nothing in a "
                f"{len(response.text)}-byte page. The layout has changed, or the list "
                "is loaded over XHR and the page HTML never contains it."
            )
    else:
        for candidate in FALLBACK_ROW_SELECTORS:
            found = soup.select(candidate)
            if len(found) >= 2:   # one row is as likely to be a header as a job
                rows, row_selector = found, candidate
                note(
                    f"no row_selector configured; fell back to {candidate!r} which matched "
                    f"{len(found)} rows. Pin this in sources.yaml rather than relying on the guess."
                )
                break
        if not rows:
            raise AdapterError(
                f"{source['key']}: no configured row_selector and none of the fallback "
                f"selectors matched ({', '.join(FALLBACK_ROW_SELECTORS)}). If the page is "
                "an XHR app, this source belongs on a JSON adapter instead."
            )

    fields = spec.get("fields") or {}
    header_map = _header_map(soup, row_selector) if not fields else {}
    if header_map:
        note(f"inferred columns from table header: {header_map}")

    postings: list[Posting] = []
    skipped = 0

    for row in rows:
        cells = row.select("td") or row.select("th")

        def by_field(name: str) -> str:
            node = _cell(row, fields.get(name))
            if node is not None:
                return _text(node)
            index = header_map.get(name)
            if index is not None and index < len(cells):
                return _text(cells[index])
            return ""

        title = by_field("title")
        if not title and cells:
            title = _text(cells[0])
        if not title:
            skipped += 1
            continue

        link = _cell(row, fields.get("url")) or row.select_one("a[href]")
        href = link.get("href", "") if link is not None and link.has_attr("href") else ""
        if href.startswith("/"):
            from urllib.parse import urljoin
            href = urljoin(url, href)

        postings.append(
            Posting(
                source_key=source["key"],
                title=title,
                url=href,
                location=by_field("location"),
                country=source.get("country", ""),
                department=by_field("department"),
                posted_at=parse_date(by_field("posted_at")),
                closing_at=parse_date(by_field("closing_at")),
            )
        )

    if skipped:
        note(f"{skipped} row(s) had no readable title and were skipped (header or spacer rows)")
    if not postings:
        raise AdapterError(
            f"{source['key']}: {len(rows)} row(s) matched {row_selector!r} but none yielded "
            "a title -- the selector is matching the wrong element"
        )
    return postings
