#!/usr/bin/env python3
"""
Offline tests for the HTML extraction layers.

Run directly -- no pytest required, no network:

    python tests/test_extraction.py

The fixtures in tests/fixtures/ represent the CMS families the donor portals
actually use (Drupal views, Bootstrap cards, header tables, Next.js embedded
JSON, JSON-LD, RSS, RTL Arabic, German date formats) plus the two failure modes
that need different fixes (bot wall, JavaScript shell). If a portal redesigns
into one of these shapes, the cascade should still find the notices.
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from portals import harvester, htmlkit  # noqa: E402
from portals.base import parse_date, parse_value_usd  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"

_passed = 0
_failed: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passed
    if condition:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed.append(name)
        print(f"  FAIL  {name}{('  -- ' + detail) if detail else ''}")


def load(filename: str) -> str:
    return (FIXTURES / filename).read_text(encoding="utf-8")


def titles(rows: list[dict]) -> list[str]:
    return [r["title"] for r in rows]


# --------------------------------------------------------------------------
def test_selector_layer() -> None:
    print("\nCSS selector layer (Drupal views)")
    html = load("drupal_views.html")
    rows = htmlkit.rows_from_selectors(html, "https://example.org/", ["div.views-row"])
    check("finds 3 rows", len(rows) == 3, f"got {len(rows)}")
    check("resolves relative URLs",
          any(r["url"].startswith("https://example.org/procurement/notice/") for r in rows))
    check("captures row text for date extraction",
          any("Deadline" in r["text"] for r in rows))


def test_table_layer() -> None:
    print("\nHeader-aware table layer")
    rows = htmlkit.rows_from_tables(load("table_listing.html"), "https://example.org/")
    check("finds 3 rows", len(rows) == 3, f"got {len(rows)}")
    first = next((r for r in rows if "Digital Government" in r["title"]), None)
    check("maps Deadline column", bool(first) and first["fields"].get("closing_date") == "2026-11-30",
          str(first["fields"]) if first else "row missing")
    check("maps Published column", bool(first) and first["fields"].get("posted_date") == "2026-07-20")
    check("maps Value column", bool(first) and "2,400,000" in (first["fields"].get("estimated_value") or ""))
    check("maps Type column", bool(first) and "Proposals" in (first["fields"].get("notice_type") or ""))


def test_german_table() -> None:
    print("\nGerman table (GIZ/KfW formats)")
    rows = htmlkit.rows_from_tables(load("german_table.html"), "https://giz.de/")
    check("finds 3 rows", len(rows) == 3, f"got {len(rows)}")
    row = next((r for r in rows if "Verwaltungsreform" in r["title"]), None)
    check("maps Abgabefrist -> closing_date",
          bool(row) and row["fields"].get("closing_date") == "31.03.2027",
          str(row["fields"]) if row else "missing")
    check("German long date parses",
          parse_date(row["fields"].get("posted_date")) == "2027-01-15" if row else False)
    check("dot-thousands value parses",
          parse_value_usd(row["fields"].get("estimated_value")) == 1635000.0 if row else False)


def test_json_layer() -> None:
    print("\nEmbedded JSON layer (__NEXT_DATA__)")
    rows = htmlkit.extract_embedded_json(load("nextjs_json.html"), "https://example.org/")
    check("finds all 3 notices", len(rows) == 3, f"got {len(rows)}")
    row = next((r for r in rows if "Social Protection" in r["title"]), None)
    check("extracts deadline", bool(row) and row["fields"].get("closing_date") == "2026-12-15")
    check("extracts posted date", bool(row) and row["fields"].get("posted_date") == "2026-08-01")
    check("extracts value", bool(row) and "1,750,000" in (row["fields"].get("estimated_value") or ""))
    check("resolves URL", bool(row) and row["url"] == "https://example.org/notices/7001")


def test_ldjson_layer() -> None:
    print("\nJSON-LD layer")
    rows = htmlkit.extract_embedded_json(load("ldjson.html"), "https://example.org/")
    check("finds 2 notices", len(rows) == 2, f"got {len(rows)}")
    check("uses headline as title", any("Governance Advisory" in t for t in titles(rows)))


def test_feed_layer() -> None:
    print("\nRSS feed layer")
    rows = htmlkit.parse_feed(load("feed.xml"), "https://example.org/")
    check("finds 2 items", len(rows) == 2, f"got {len(rows)}")
    check("keeps link", any(r["url"] == "https://example.org/feed/1" for r in rows))
    check("captures pubDate", all(r["fields"].get("posted_date") for r in rows))
    posted, closing = htmlkit.resolve_dates(rows[0])
    check("deadline recovered from description", parse_date(closing) == "2026-11-30",
          f"closing={closing}")


def test_feed_discovery() -> None:
    print("\nFeed discovery")
    feeds = htmlkit.discover_feeds(load("drupal_views.html"), "https://example.org/page")
    check("finds advertised feed", feeds == ["https://example.org/procurement/feed.xml"], str(feeds))


def test_structural_layer() -> None:
    print("\nStructural inference (no class names at all)")
    rows = htmlkit.rows_from_structure(load("unknown_layout.html"), "https://example.org/")
    check("recovers 4 rows without selectors", len(rows) == 4, f"got {len(rows)}")
    check("titles intact", any("Business Process Reengineering" in t for t in titles(rows)))
    check("row text carries the deadline", any("28 November 2026" in r["text"] for r in rows))


def test_structural_scale() -> None:
    print("\nStructural inference on a large listing (regression: a size guard")
    print("once skipped containers with >400 children, silently returning 0 rows)")
    import time

    for count in (50, 500, 2000):
        markup = "".join(
            f'<div class="r"><span><a href="/n/{i}">Jordan advisory services notice {i}</a>'
            f"</span><em>Deadline: 30 November 2026</em></div>"
            for i in range(count)
        )
        page = (f"<html><body><main><div><div>{markup}</div></div>"
                + "<div><p>filler</p></div>" * 800 + "</main></body></html>")
        started = time.time()
        rows = htmlkit.rows_from_structure(page, "https://example.org/")
        elapsed = time.time() - started
        check(f"{count} notices recovered", len(rows) == count, f"got {len(rows)}")
        check(f"{count} notices under 15s", elapsed < 15, f"took {elapsed:.1f}s")


def test_country_matching() -> None:
    print("\nCountry matching precision (word boundaries, not substrings)")
    from portals.base import mentions_jordan

    for text, want in (
        ("Consulting Services, Jordan", True),
        ("Water project in Amman", True),
        ("خدمات استشارية في الأردن", True),
        ("المملكة الأردنية الهاشمية", True),
        ("Contact: procurement@mof.gov.jo", True),
        ("Road resurfacing, Jordanstown, Northern Ireland", False),
        ("Community centre, Ammanford, Wales", False),
        ("Contact: jordan.smith@contractor.co.uk", False),
    ):
        check(f"{'matches' if want else 'rejects'}: {text[:42]}",
              mentions_jordan(text) is want)


def test_arabic() -> None:
    print("\nArabic RTL listing")
    rows = htmlkit.rows_from_selectors(load("arabic_rtl.html"), "https://sfd.gov.sa/", ["div.tender-card"])
    check("finds 3 rows", len(rows) == 3, f"got {len(rows)}")
    row = next((r for r in rows if "المياه" in r["title"]), None)
    posted, closing = htmlkit.resolve_dates(row) if row else (None, None)
    check("Arabic labelled deadline found", closing is not None, f"closing={closing}")
    check("Arabic date parses to ISO", parse_date(closing) == "2026-09-30", f"parsed={parse_date(closing)}")
    check("Arabic posted date parses", parse_date(posted) == "2026-07-15", f"parsed={parse_date(posted)}")


def test_diagnosis() -> None:
    print("\nFailure diagnosis (distinguishes bot wall from layout change)")
    wall = htmlkit.diagnose(load("cloudflare_wall.html"))
    check("detects bot protection", bool(wall) and "bot protection" in wall, str(wall))
    shell = htmlkit.diagnose(load("js_shell.html"))
    check("detects JavaScript shell", bool(shell) and "playwright" in shell.lower(), str(shell))
    check("healthy page returns None", htmlkit.diagnose(load("table_listing.html")) is None)


def test_pagination() -> None:
    print("\nPagination")
    nxt = htmlkit.find_next_page(load("paginated_p1.html"), "https://example.org/paginated_p1.html")
    check("follows rel=next", nxt == "https://example.org/paginated_p2.html", str(nxt))
    check("no next on last page", htmlkit.find_next_page(load("table_listing.html"), "https://x/") is None)


def test_site_ldjson_does_not_hijack() -> None:
    print("\nSite-level JSON-LD must not be mistaken for notices")
    html = load("site_ldjson_plus_listing.html")
    json_rows = htmlkit.extract_embedded_json(html, "https://www.ebrd.com/")
    check("Organization/BreadcrumbList blocks rejected", json_rows == [],
          f"got {titles(json_rows)}")
    rows = htmlkit.extract_rows(html, "https://www.ebrd.com/",
                                selectors=["div.notice-row"])
    check("cascade falls through to the real listing",
          len(rows) == 3 and rows[0]["source"].startswith("selector"),
          f"{len(rows)} rows via {rows[0]['source'] if rows else 'none'}")
    check("real notice titles recovered",
          any("Transaction Advisory" in t for t in titles(rows)))


def test_quality_gate_blocks_bad_selector() -> None:
    print("\nQuality gate: an over-broad selector must not beat a better layer")
    html = load("selector_hijack.html")

    hijack = htmlkit.rows_from_selectors(html, "https://example.org/", ["article"])
    check("bare 'article' does match the nav teasers", len(hijack) == 3, f"got {len(hijack)}")
    check("...but scores as a poor listing",
          htmlkit.listing_quality(hijack) < htmlkit.QUALITY_THRESHOLD,
          f"quality {htmlkit.listing_quality(hijack)}")

    real = htmlkit.rows_from_tables(html, "https://example.org/")
    check("the real table listing scores well",
          htmlkit.listing_quality(real) >= htmlkit.QUALITY_THRESHOLD,
          f"quality {htmlkit.listing_quality(real)}")

    rows = htmlkit.extract_rows(html, "https://example.org/", selectors=["article"])
    check("cascade skips the selector layer", rows and rows[0]["source"] == "table",
          f"chose {rows[0]['source'] if rows else 'nothing'}")
    check("real notices recovered",
          any("Institutional Reform" in r["title"] for r in rows))


def test_selector_suggestion() -> None:
    print("\nSelector suggestion (powers `run.py --capture`)")
    suggested = htmlkit.suggest_selectors(load("drupal_views.html"))
    check("suggests the real listing class", any("views-row" in s for s in suggested),
          str(suggested))
    report = htmlkit.analyse_page(load("table_listing.html"), "https://example.org/",
                                  selectors=["div.nope"])
    check("analyse_page names the winning layer", report["chosen_layer"] == "table",
          str(report["chosen_layer"]))
    check("analyse_page reports per-layer counts", report["layers"]["tables"]["rows"] == 3,
          str(report["layers"]["tables"]))


def test_cascade_order() -> None:
    print("\nCascade picks the best available layer")
    rows = htmlkit.extract_rows(load("nextjs_json.html"), "https://example.org/",
                                selectors=["div.nope"], href_pattern=r"/notices/")
    check("prefers embedded JSON over anchors", rows and rows[0]["source"] == "json",
          rows[0]["source"] if rows else "no rows")
    rows = htmlkit.extract_rows(load("unknown_layout.html"), "https://example.org/",
                                selectors=["div.does-not-exist"])
    check("falls through to structural inference",
          rows and rows[0]["source"] == "structure", rows[0]["source"] if rows else "no rows")
    rows = htmlkit.extract_rows(load("bootstrap_cards.html"), "https://example.org/",
                                selectors=["div.card"])
    check("uses selectors when they match", rows and rows[0]["source"].startswith("selector"),
          rows[0]["source"] if rows else "no rows")


def test_href_patterns_match_real_urls() -> None:
    """
    Each portal's HREF_PATTERN must match notice URLs actually observed on that
    portal (collected via web search in August 2026 -- these are real permalinks,
    not invented examples). This is the one part of the scrapers validated
    against the live web rather than against fixtures.
    """
    print("\nHREF patterns vs real notice URLs observed in the wild")
    import re

    from portals import ebrd, eib, giz, isdb, jica, sfd, ungm

    real_urls = [
        (ungm, "https://www.ungm.org/Public/Notice/274472"),
        (ungm, "https://www.ungm.org/Public/Notice/166937"),
        (ebrd, "https://ecepp.ebrd.com/delta/viewNotice.html?displayNoticeId=39536445"),
        (ebrd, "https://www.ebrd.com/home/work-with-us/project-procurement/procurement-notices.html"),
        (eib, "https://www.eib.org/en/about/procurement/calls/all/cft-1744"),
        (eib, "https://www.eib.org/en/about/procurement/calls-technical-assistance/all/aa-011624003"),
        (isdb, "https://www.isdb.org/project-procurement/tenders/2026/gpn/"
               "islamic-finance-legal-framework-guidelines-and-database-project-gpn"),
        (giz, "https://www.giz.de/en/invitation-tender-7000004018-supply-and-delivery-"
              "document-and-epassport-reader"),
        (giz, "https://www.giz.de/en/procurement-goods-supply-it-equipment-software"),
        (sfd, "https://www.sfd.gov.sa/en/tenders-view"),
        (jica, "https://www.jica.go.jp/jordan/english/office/others/procurement.html"),
    ]
    for module, url in real_urls:
        pattern = getattr(module, "HREF_PATTERN", None)
        matched = bool(pattern and re.search(pattern, url, re.IGNORECASE))
        check(f"{module.PORTAL_KEY}: {url[:58]}", matched,
              f"pattern {pattern!r} did not match")


def test_harvest_end_to_end(monkeypatched: dict) -> None:
    print("\nHarvester end-to-end (fixtures served instead of the network)")
    tenders = harvester.harvest(
        portal_key="giz",
        label="Fixture Portal",
        sources=[harvester.Source("https://fixture.test/drupal_views.html")],
        selectors=["div.views-row"],
        href_pattern=r"/notice/\d+",
        notice_type="Fixture notice",
        manual_url="https://fixture.test/",
        use_feeds=False,
        enrich=False,
    )
    check("keeps only Jordan tenders", len(tenders) == 2, f"got {len(tenders)}: {titles(tenders)}")
    check("drops the Morocco notice", not any("Morocco" in t["title"] for t in tenders))
    row = next((t for t in tenders if "Public Financial Management" in t["title"]), None)
    check("closing date parsed", bool(row) and row["closing_date"] == "2026-09-30",
          str(row.get("closing_date")) if row else "missing")
    check("posted date parsed", bool(row) and row["posted_date"] == "2026-07-12")
    check("standard schema present",
          bool(row) and all(k in row for k in
                            ("id", "title", "portal", "url", "posted_date", "closing_date",
                             "estimated_value_usd", "sector", "description", "language")))
    value_row = next((t for t in tenders if "Water Network" in t["title"]), None)
    check("value extracted from free text",
          bool(value_row) and value_row["estimated_value_usd"] == 1200000.0,
          str(value_row.get("estimated_value_usd")) if value_row else "missing")


def test_harvest_reports_bot_wall(monkeypatched: dict) -> None:
    print("\nHarvester surfaces an actionable reason, not a generic failure")
    from portals.base import PortalError

    try:
        harvester.harvest(
            portal_key="ebrd",
            label="Fixture Portal",
            sources=[harvester.Source("https://fixture.test/cloudflare_wall.html")],
            selectors=["div.nope"],
            manual_url="https://fixture.test/",
            use_feeds=False,
            enrich=False,
        )
        check("raises PortalError", False, "no exception raised")
    except PortalError as exc:
        check("raises PortalError", True)
        check("names bot protection as the cause", "bot protection" in str(exc), str(exc)[:160])
        check("includes a manual-check URL", "fixture.test" in str(exc))


# --------------------------------------------------------------------------
def main() -> int:
    # Serve fixtures instead of making network calls
    served: dict = {}

    def fake_fetch(url: str, *, params=None, js: bool = False) -> str:
        name = url.rsplit("/", 1)[-1]
        served[name] = served.get(name, 0) + 1
        path = FIXTURES / name
        if not path.exists():
            raise RuntimeError(f"no fixture for {url}")
        return path.read_text(encoding="utf-8")

    htmlkit.fetch_html = fake_fetch  # type: ignore[assignment]

    print("=" * 74)
    print("HTML extraction tests -- offline, no network")
    print("=" * 74)

    test_selector_layer()
    test_table_layer()
    test_german_table()
    test_json_layer()
    test_ldjson_layer()
    test_feed_layer()
    test_feed_discovery()
    test_structural_layer()
    test_structural_scale()
    test_country_matching()
    test_arabic()
    test_diagnosis()
    test_pagination()
    test_site_ldjson_does_not_hijack()
    test_quality_gate_blocks_bad_selector()
    test_selector_suggestion()
    test_cascade_order()
    test_href_patterns_match_real_urls()
    test_harvest_end_to_end(served)
    test_harvest_reports_bot_wall(served)

    print("\n" + "=" * 74)
    total = _passed + len(_failed)
    if _failed:
        print(f"{_passed}/{total} passed, {len(_failed)} FAILED:")
        for name in _failed:
            print(f"  - {name}")
        return 1
    print(f"All {total} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
