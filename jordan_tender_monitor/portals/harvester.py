"""
Generic driver for HTML portals.

A portal declares a HtmlSpec -- its source URLs, its selector hints and its
currency -- and this module does the fetching, the cascade, pagination and
detail enrichment. Most portals declare theirs as data in `portals.json` and
have no module at all; `spec_for()` below is what turns one into a spec.
Portals that need custom logic (UNGM's POST search endpoint, the REST APIs)
supply their own fetch function instead, but still route the resulting HTML
through here so that --capture works for every HTML portal rather than only the
simple ones.

THE SELECTORS ARE HINTS, NOT CONTRACTS. They were written without access to the
live pages -- see the README. If a hint is wrong the quality gate rejects it and
a class-independent layer takes over, which is the whole reason the cascade
exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import config, portal_config
from ..utils.text import clean
from . import base
from .htmlkit import LayerResult, extract, run_layers


@dataclass
class HtmlSpec:
    """Everything the generic driver needs to read one portal."""

    key: str
    urls: list[str]
    selectors: list[str] = field(default_factory=list)
    anchor_hint: str | None = None
    currency: str | None = None
    # Portals that publish worldwide need filtering down to Jordan; a
    # Jordan-specific page does not.
    filter_to_jordan: bool = True
    # Optional custom fetcher: (url) -> html. Used by portals behind a POST
    # search endpoint so that --capture can still reach them.
    fetcher: object | None = None
    # Optional per-column CSS hooks, for a listing the generic rules cannot
    # read by inference -- see htmlkit._apply_field_selectors. Applied only in
    # the selector layer, so the class-independent layers stay class-independent
    # and remain a real fallback when these stop matching.
    field_selectors: dict = field(default_factory=dict)
    # Set for a source that publishes no listing at all, so an empty result is
    # reported as "no listing published" rather than as a broken scraper. See
    # the ADFD and JICA entries in portals.json.
    no_listing_reason: str = ""
    notes: str = ""


def spec_for(key: str, **overrides) -> HtmlSpec:
    """Build a portal's spec from portals.json, with code-owned overrides.

    A module passes only the fields it owns -- UNGM's selectors, for instance,
    which were derived from the live DOM and carry their reasoning in the
    module. Everything else comes from the file, so a URL can be corrected from
    a phone without a code change.

    An unknown key yields a spec with no URLs rather than raising: this runs at
    import time, and an ImportError here would turn one bad entry into a run
    that produces nothing at all. harvest() reports the empty spec as the
    configuration error it is.
    """
    portal = portal_config.get(key)
    if portal is None:
        return HtmlSpec(key=key, urls=[], **overrides)

    fields = {
        "urls": list(portal.urls),
        "selectors": list(portal.selectors),
        "field_selectors": dict(portal.field_selectors),
        "anchor_hint": portal.anchor_hint,
        "currency": portal.currency,
        "filter_to_jordan": portal.filter_to_jordan,
        "no_listing_reason": portal.no_listing_reason,
        "notes": portal.notes,
    }
    fields.update(overrides)
    return HtmlSpec(key=key, **fields)


def _fetch(spec: HtmlSpec, url: str) -> str:
    if spec.fetcher is not None:
        return spec.fetcher(url)
    return base.fetch(url)


def _next_page(html: str, current_url: str) -> str | None:
    """Find a 'next page' link without relying on class names."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        label = clean(a.get_text()).lower()
        rel = " ".join(a.get("rel") or []).lower()
        aria = clean(a.get("aria-label") or "").lower()
        if (rel == "next" or label in {"next", "next page", ">", "›", "»"}
                or aria in {"next", "next page"}):
            href = a["href"]
            if href and not href.startswith("#"):
                return urljoin(current_url, href)
    return None


def harvest(spec: HtmlSpec) -> list[dict]:
    """Read every source URL for a portal and return standard records.

    A single URL failing is tolerated as long as another one works -- several
    of these portals publish across two sites (GIZ, EBRD). Only a portal where
    every source failed raises, and it raises with the last diagnosed reason.
    """
    if not spec.urls:
        # A configuration fault, not a site fault, and it must not be dressed
        # as one: "no listing found" would send someone to check a portal that
        # was never asked for a page.
        raise base.PortalError(
            f"portals.json declares no source URL for '{spec.key}' -- the entry "
            f"is missing or was rejected on load", "")

    records: list[dict] = []
    failures: list[str] = []
    seen_ids: set[str] = set()

    for url in spec.urls:
        try:
            page_url = url
            for page_number in range(config.MAX_PAGINATION_PAGES if config.FOLLOW_PAGINATION else 1):
                html = _fetch(spec, page_url)
                result = extract(html, page_url, spec.selectors, spec.anchor_hint,
                                 field_selectors=spec.field_selectors)
                if not result.rows:
                    if page_number == 0:
                        failures.append(f"{page_url}: {result.note}")
                    break

                for row in result.rows:
                    record = base.row_to_record(spec.key, row, spec.currency)
                    if record["id"] in seen_ids:
                        continue
                    seen_ids.add(record["id"])
                    record["_layer"] = result.layer
                    record["_quality"] = result.quality
                    records.append(record)

                if not config.FOLLOW_PAGINATION:
                    break
                page_url = _next_page(html, page_url)
                if not page_url:
                    break
        except base.PortalError as exc:
            failures.append(f"{url}: {exc.reason}")
            continue

    if not records:
        reason = " | ".join(failures) if failures else "no notices found on any source URL"
        url = spec.urls[0] if spec.urls else ""
        if spec.no_listing_reason:
            # A source that publishes nothing is not a scraper that has stopped
            # working, and reporting it as one puts a permanent red line in
            # every report -- which is how a reader learns to ignore the status
            # table, and the status table is the alarm. The underlying reason
            # is kept, so a genuine change (a bot wall, a transport error) is
            # still visible and still distinguishable from "there is nothing
            # here".
            raise base.PortalError(
                f"no listing published - {spec.no_listing_reason} Detail: {reason}",
                url)
        raise base.PortalError(reason, url)

    if spec.filter_to_jordan:
        records = base.jordan_only(records)

    if config.ENRICH_FROM_DETAIL:
        _enrich_missing_deadlines(spec, records)

    return records


def _enrich_missing_deadlines(spec: HtmlSpec, records: list[dict]) -> None:
    """Try to recover missing deadlines from detail pages, within a budget.

    Bounded by DETAIL_FETCH_BUDGET so a portal with a hundred undated notices
    cannot turn one run into a hundred extra requests. Notices left undated are
    kept and flagged, never dropped (Q6).
    """
    budget = config.DETAIL_FETCH_BUDGET
    for record in records:
        if budget <= 0:
            break
        if record.get("closing_date") or not record.get("url"):
            continue
        try:
            html = _fetch(spec, record["url"])
        except base.PortalError:
            budget -= 1
            continue
        budget -= 1

        detail = extract(html, record["url"], spec.selectors, spec.anchor_hint,
                         field_selectors=spec.field_selectors)
        text = clean(BeautifulSoup(html, "html.parser").get_text(" "))
        from .htmlkit import Row, _assign_labelled_fields  # local: internal helper
        probe = Row(title=record["title"], raw_text=text)
        _assign_labelled_fields(probe, text)
        from ..utils.dates import parse_date
        closing = parse_date(probe.closing_text)
        if closing:
            record["closing_date"] = closing
        if record.get("estimated_value_usd") is None and probe.value_text:
            from ..utils import money
            record["estimated_value_usd"] = money.parse_value_usd(
                probe.value_text, spec.currency)
        if detail.rows and not record.get("description"):
            record["description"] = detail.rows[0].description


def capture(spec: HtmlSpec) -> list[tuple[str, str, list[LayerResult]]]:
    """Fetch a portal's live pages and report every layer's result.

    This is how an unverified selector hint gets confirmed in one command.
    Returns (url, html, layer_results) per source URL. Works for every HTML
    portal, including those with a custom fetcher -- portals with bespoke fetch
    logic are exactly the ones most likely to be accidentally excluded from a
    diagnostic like this.
    """
    out = []
    for url in spec.urls:
        try:
            html = _fetch(spec, url)
        except base.PortalError as exc:
            out.append((url, "", [LayerResult("error", [], 0.0, exc.reason)]))
            continue
        out.append((url, html, run_layers(html, url, spec.selectors,
                                          spec.anchor_hint,
                                          spec.field_selectors)))
    return out
