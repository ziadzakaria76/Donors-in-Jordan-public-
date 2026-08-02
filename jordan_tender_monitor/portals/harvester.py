"""
Shared harvest pipeline for the HTML-scraping portals.

Each portal declares *what* to scrape (sources, selector hints, notice type) and
this module handles *how*: feed discovery, the extraction cascade, pagination,
Jordan filtering, detail-page enrichment and error diagnosis. Hardening applied
here benefits all ten scrapers at once, which is the point -- these portals fail
in the same handful of ways.
"""

from __future__ import annotations

import logging

import config

from . import htmlkit
from .base import PortalError, clean_text, detect_language, make_record, mentions_jordan

log = logging.getLogger(__name__)


class Source:
    """One page to scrape."""

    def __init__(self, url: str, *, js: bool = False, params: dict | None = None):
        self.url = url
        self.js = js
        self.params = params


def _collect_from_source(
    source: Source,
    *,
    selectors: list[str],
    href_pattern: str | None,
    use_feeds: bool,
    errors: list[str],
) -> tuple[list[dict], str]:
    """Rows from one source, following pagination. Returns (rows, last_html)."""
    rows: list[dict] = []
    last_html = ""
    url = source.url
    params = source.params

    for page_number in range(config.MAX_PAGINATION_PAGES if config.FOLLOW_PAGINATION else 1):
        try:
            html = htmlkit.fetch_html(url, params=params, js=source.js)
        except Exception as exc:  # noqa: BLE001 - try the next source
            errors.append(f"{url}: {exc}")
            break
        last_html = html
        params = None  # query params belong to the first request only

        # A published feed beats scraping, and survives redesigns.
        if use_feeds and page_number == 0:
            for feed_url in htmlkit.discover_feeds(html, url)[:2]:
                try:
                    feed_rows = htmlkit.parse_feed(htmlkit.fetch_html(feed_url), feed_url)
                except Exception as exc:  # noqa: BLE001
                    log.debug("feed %s failed: %s", feed_url, exc)
                    continue
                if feed_rows:
                    log.info("%s: %d rows from feed %s", source.url, len(feed_rows), feed_url)
                    rows.extend(feed_rows)

        page_rows = htmlkit.extract_rows(
            html, url, selectors=selectors, href_pattern=href_pattern
        )
        rows.extend(page_rows)

        if not page_rows or not config.FOLLOW_PAGINATION:
            break
        next_url = htmlkit.find_next_page(html, url)
        if not next_url or not htmlkit.same_host(next_url, url) or next_url == url:
            break
        url = next_url

    return rows, last_html


def harvest(
    *,
    portal_key: str,
    label: str,
    sources: list[Source],
    selectors: list[str],
    href_pattern: str | None = None,
    notice_type: str = "",
    manual_url: str = "",
    use_feeds: bool = True,
    require_jordan: bool = True,
    default_eligibility: str | None = None,
    enrich: bool | None = None,
) -> list[dict]:
    """Scrape every source and return standardised tender records."""
    all_rows: list[dict] = []
    errors: list[str] = []
    parsed_any = False
    last_html = ""

    for source in sources:
        rows, html = _collect_from_source(
            source,
            selectors=selectors,
            href_pattern=href_pattern,
            use_feeds=use_feeds,
            errors=errors,
        )
        if html:
            last_html = html
        if rows:
            parsed_any = True
            all_rows.extend(rows)

    if not parsed_any:
        reason = htmlkit.diagnose(last_html) if last_html else None
        detail = reason or (
            "no extraction layer (feed, JSON, selectors, tables, structure, anchors) "
            "could parse a notice row"
        )
        raise PortalError(
            f"{label}: {detail}. "
            + (f"Transport errors: {'; '.join(errors[:3])}. " if errors else "")
            + f"Check manually: {manual_url or (sources[0].url if sources else '')}"
        )

    # Deduplicate within the portal, preferring rows that carry structured fields
    by_url: dict[str, dict] = {}
    for row in all_rows:
        key = row.get("url") or row.get("title", "")
        existing = by_url.get(key)
        if existing is None or len(row.get("fields") or {}) > len(existing.get("fields") or {}):
            if existing:
                row.setdefault("text", "")
                row["text"] = f"{row['text']} | {existing.get('text', '')}"
            by_url[key] = row
    rows = list(by_url.values())

    if require_jordan:
        rows = [r for r in rows if mentions_jordan(r.get("title", ""), r.get("text", ""))]

    do_enrich = config.ENRICH_FROM_DETAIL if enrich is None else enrich
    if do_enrich:
        budget = [config.DETAIL_FETCH_BUDGET]
        for row in rows:
            if budget[0] <= 0:
                break
            htmlkit.enrich_from_detail(row, budget)

    tenders: list[dict] = []
    for row in rows:
        posted, closing = htmlkit.resolve_dates(row)
        fields = row.get("fields") or {}
        text = row.get("text") or row.get("title", "")
        tenders.append(
            make_record(
                portal_key=portal_key,
                title=row["title"],
                url=row.get("url", ""),
                posted_date=posted,
                closing_date=closing,
                estimated_value=fields.get("estimated_value") or text,
                description=clean_text(text)[:1500],
                notice_type=fields.get("notice_type") or notice_type,
                eligibility=default_eligibility,
                language=detect_language(row["title"], text),
            )
        )

    log.info("%s: %d Jordan notices retrieved (%d rows before country filter)",
             label, len(tenders), len(all_rows))
    return tenders
