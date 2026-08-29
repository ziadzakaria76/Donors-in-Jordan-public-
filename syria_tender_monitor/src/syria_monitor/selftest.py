r"""Offline self-test: the whole pipeline over committed fixtures.

This is what stands in for a live dry run in an environment with no network. It
proves the wiring end to end -- extraction, the country gate, classification,
deadline filtering, dedupe, ranking and the four-way classification split -- and
it runs with the database and output directory redirected, so it can never write
fixture ids into real state. With NEW-marking on, that would make the next real
run report nothing and look exactly like a broken monitor.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from .fetch import Fetcher, Response
from .portals.base import HtmlPortal

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


class _FixtureFetcher(Fetcher):
    def __init__(self, html: str):
        super().__init__()
        self._html = html

    def get(self, url, **kwargs):
        return Response(url=url, status=200, text=self._html, headers={})

    def post(self, url, **kwargs):
        return self.get(url, **kwargs)


def _fixture_portal(name: str, filename: str):
    class FixturePortal(HtmlPortal):
        pass

    FixturePortal.name = name
    FixturePortal.label = f"fixture:{name}"
    # A synthetic but well-formed https base, so the relative hrefs inside the
    # fixtures resolve the way a real portal's would. The pages still come from
    # disk -- nothing is fetched. With a fixture:// base every notice URL came
    # out unusable and the report showed "no link published" for all of them,
    # which says more about the harness than about the writer.
    FixturePortal.url = f"https://fixtures.example/{filename}"
    FixturePortal.__doc__ = f"Serves tests/fixtures/{filename}."

    def pages(self):
        return [("index", FixturePortal.url)]

    def fetch_page(self, label, url):
        return (FIXTURES / filename).read_text(encoding="utf-8"), 200

    def row_to_record(self, row, page_url):
        record = HtmlPortal.row_to_record(self, row, page_url)
        # These fixtures write the delivery country in prose ("Place of
        # performance: X"), which stands in for the country field a real API
        # returns -- the point being that the gate reads a FIELD, not the text.
        import re
        match = re.search(r"Place of performance:\s*([^.]+)\.", row.text)
        if match:
            record["place_of_performance_country"] = match.group(1).strip()
        return record

    FixturePortal.pages = pages
    FixturePortal.row_to_record = row_to_record
    FixturePortal.fetch_page = fetch_page
    return FixturePortal


FIXTURE_PORTALS = {
    "fx_drupal": _fixture_portal("fx_drupal", "drupal_views.html"),
    "fx_cards": _fixture_portal("fx_cards", "bootstrap_cards.html"),
    "fx_table": _fixture_portal("fx_table", "giz_header_table.html"),
    "fx_nextjs": _fixture_portal("fx_nextjs", "nextjs.html"),
    "fx_jsonld": _fixture_portal("fx_jsonld", "jsonld_site_only.html"),
    "fx_arabic": _fixture_portal("fx_arabic", "arabic_rtl.html"),
    "fx_navtrap": _fixture_portal("fx_navtrap", "nav_trap.html"),
    # Covers all four classification categories plus the Blantyre false
    # positive, so the split below demonstrates the classifier rather than
    # just counting one category.
    "fx_mixed": _fixture_portal("fx_mixed", "mixed_scope.html"),
    "fx_wall": _fixture_portal("fx_wall", "cloudflare_wall.html"),      # must report unavailable
}


def self_test(cfg, today: date | None = None) -> int:
    from .models import LINK_TYPES
    from .pipeline import run as run_pipeline
    from .portals import REGISTRY
    from .report.common import LINK_LABELS
    from .state import SeenStore

    workspace = Path(tempfile.mkdtemp(prefix="syria-selftest-"))
    print(f"Self-test workspace (real state untouched): {workspace}")

    original = dict(REGISTRY)
    REGISTRY.clear()
    REGISTRY.update(FIXTURE_PORTALS)
    store = SeenStore(workspace / "selftest.db", read_only=True)
    try:
        result = run_pipeline(cfg, fetcher=Fetcher(), store=store,
                              today=today or date(2026, 8, 23),
                              portals=list(FIXTURE_PORTALS))
    finally:
        REGISTRY.clear()
        REGISTRY.update(original)

    print("\n" + result.subject())
    print("-" * 78)
    for portal in result.portals:
        print("  " + portal.status_line)
    print("-" * 78)
    print("Classification split (every category, including those out of scope):")
    for key in LINK_TYPES:
        print(f"  {LINK_LABELS.get(key, key):<32} {result.counts.get(key, 0)}")
    print(f"  in scope: {len(result.tenders)} | excluded but logged: {len(result.excluded)} "
          f"| duplicates collapsed: {result.duplicates_collapsed} "
          f"| expired dropped: {result.expired_dropped}")
    print("-" * 78)
    for rank, tender in enumerate(result.tenders[:10], start=1):
        closing = tender.closing_date.isoformat() if tender.closing_date else "not published"
        print(f"{rank:>3}. [{tender.score:5.1f}] {tender.title[:58]}")
        print(f"          {tender.portal} | closes {closing} | {tender.syria_link_type} "
              f"| lang {tender.language}")

    assert store.record(result.tenders) == 0, "self-test must never write to a seen database"
    store.close()

    # Sample outputs go to the throwaway workspace, not output/, so the report
    # format can be reviewed without a network run and without touching
    # anything the real run owns.
    from .report import write_docx, write_json, write_xlsx
    written = [
        write_docx(result, workspace / "sample-report.docx", cfg.get("output.top_n", 10)),
        write_xlsx(result, workspace / "sample-report.xlsx"),
        write_json(result, workspace / "sample-report.json", cfg.profile),
    ]
    print("\nSample outputs (fixture data, not live):")
    for path in written:
        print(f"  {path}")
    print("\nSelf-test complete. Nothing written to real state; no network used.")
    return 0
