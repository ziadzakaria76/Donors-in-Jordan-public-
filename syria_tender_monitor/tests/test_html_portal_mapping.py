"""Field mapping for the six HTML portals.

Each portal parses a page in the shape its site is assumed to use, and the
mapped fields are asserted end to end: title, absolute URL, closing date, value,
and the country gate's verdict.

IMPORTANT: the pages under tests/fixtures/html/ are RECONSTRUCTIONS. No portal
was reachable from the environment this was written in, and no CSS selectors are
shipped, so what these tests really pin is the behaviour of the
class-independent extraction layers plus each portal's own rules. Replace a
fixture with real `--capture` output and a failure here names the mapping that
was wrong. Provenance is in tests/fixtures/html/README.md.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from syria_monitor.fetch import Fetcher, Response
from syria_monitor.portals import HTML_PORTALS, REGISTRY

HTML_FIXTURES = Path(__file__).parent / "fixtures" / "html"

# The base each portal's relative hrefs resolve against, so the assertions can
# check absolute URLs the way a reader would follow them.
BASES = {
    "ungm": "https://www.ungm.org/Public/Notice/Search",
    "undp": "https://procurement-notices.undp.org/",
    "srtf": "https://www.srtfund.org/procurements/list",
    "giz": "https://ausschreibungen.giz.de/",
    "isdb": "https://www.isdb.org/project-procurement/tenders",
    "gtai": "https://www.gtai.de/en/trade/tenders",
}


class PageFetcher(Fetcher):
    def __init__(self, html: str):
        super().__init__()
        self.html = html

    def get(self, url, **kwargs):
        return Response(url=url, status=200, text=self.html, headers={})

    def post(self, url, **kwargs):
        return self.get(url, **kwargs)


def page(name: str) -> str:
    return (HTML_FIXTURES / f"{name}.html").read_text(encoding="utf-8")


def collect(name, profile, gate, cfg=None):
    portal = REGISTRY[name](cfg or {}, profile, PageFetcher(page(name)), gate)
    return portal.collect()


def titled(outcome, fragment):
    matches = [t for t in outcome.tenders if fragment.lower() in t.title.lower()]
    assert matches, f"no kept tender matching {fragment!r}: {[t.title for t in outcome.tenders]}"
    return matches[0]


UNGM_CFG = {"country_id": 2401}


@pytest.fixture
def outcomes(profile, gate):
    return {name: collect(name, profile, gate, UNGM_CFG if name == "ungm" else {})
            for name in HTML_PORTALS}


# --------------------------------------------------------------- every portal
@pytest.mark.parametrize("name", HTML_PORTALS)
def test_every_html_portal_extracts_rows_without_shipped_selectors(name, outcomes):
    """No CSS selectors are shipped, so this is the class-independent cascade."""
    outcome = outcomes[name]
    assert outcome.available, outcome.error
    assert outcome.stats.seen >= 3, f"{name} parsed {outcome.stats.seen} rows"
    assert outcome.tenders, f"{name} kept nothing"


@pytest.mark.parametrize("name", HTML_PORTALS)
def test_every_html_portal_drops_the_non_syria_row(name, outcomes):
    outcome = outcomes[name]
    assert outcome.stats.seen > len(outcome.tenders), (
        f"{name} kept every row -- the country gate did nothing")


@pytest.mark.parametrize("name", HTML_PORTALS)
def test_every_kept_row_has_an_absolute_url_on_the_portal_host(name, outcomes):
    from urllib.parse import urlparse
    expected_host = urlparse(BASES[name]).netloc
    for tender in outcomes[name].tenders:
        assert tender.url, f"{name}: {tender.title} has no url"
        assert urlparse(tender.url).netloc == expected_host, tender.url


@pytest.mark.parametrize("name", HTML_PORTALS)
def test_every_kept_row_carries_a_deadline(name, outcomes):
    """A date silently lost to a parsing bug reads as "no deadline", and the
    tender then survives on a technicality rather than being verifiable."""
    undated = [t.title for t in outcomes[name].tenders if t.closing_date is None]
    if name == "giz":
        assert len(undated) <= 1, undated       # the unclosed-cell row has "n.v."
    else:
        assert not undated, undated


# ----------------------------------------------------------------------- UNGM
def test_ungm_reads_the_real_deadline_not_the_publication_date(outcomes):
    """The row carries "Deadline: 30-Sep-2026 Expires in 38 days Published:
    20-Jul-2026". Taking the next date after a closing label lands on the
    publication date, which is in the past, so the row is dropped as closed --
    and the portal's whole open pipeline disappears silently."""
    tender = titled(outcomes["ungm"], "water pumping stations")
    assert tender.closing_date == date(2026, 9, 30)
    assert tender.closing_date != date(2026, 7, 20)


def test_ungm_builds_notice_urls_from_its_anchor_pattern(outcomes):
    assert titled(outcomes["ungm"], "water pumping stations").url == \
        "https://www.ungm.org/Public/Notice/245871"


def test_ungm_keeps_a_title_that_names_no_country(outcomes):
    assert titled(outcomes["ungm"], "laboratory equipment").syria_link_type == "inside_syria"


def test_ungm_declares_the_country_it_inferred_rather_than_passing_it_off(outcomes):
    """A country the portal wrote in must be distinguishable from one it read.

    The gate treats the country FIELD as authoritative, so writing one in for a
    "Multiple destinations" row manufactures its strongest signal. Keeping those
    rows is a deliberate recall choice -- the live run of 2026-08-31 kept 85 of
    85 -- but nothing downstream could tell an inferred country from a published
    one, and "85 kept of 85" reads as a portal working perfectly.
    """
    outcome = outcomes["ungm"]

    inferred = titled(outcome, "GHG Study")
    assert inferred.syria_link_type == "inside_syria", "kept, as the recall choice intends"
    assert "country_inferred:ungm_multiple_destinations" in inferred.flags

    # A row that names the country itself is NOT an inference, and must not be
    # flagged as one -- otherwise the flag means nothing.
    named = [t for t in outcome.tenders
             if not any(f.startswith("country_inferred:") for f in t.flags)]
    assert named, "every kept row was flagged inferred; the flag is not discriminating"

    # And the health line carries the count, so it is visible without opening
    # the spreadsheet.
    assert "country inferred" in outcome.status_line


def test_ungm_labels_the_jordan_row_rather_than_dropping_it(profile, gate):
    outcome = collect("ungm", profile, gate, UNGM_CFG)
    mafraq = [t for t in outcome.tenders if "Mafraq" in t.title]
    assert mafraq and mafraq[0].syria_link_type == "refugee_hosting_only"


# ----------------------------------------------------------------------- UNDP
def test_undp_uses_its_view_notice_anchor_pattern(outcomes):
    tender = titled(outcomes["undp"], "solid waste management")
    assert tender.url == "https://procurement-notices.undp.org/view_notice.cfm?notice_id=118842"
    assert tender.closing_date == date(2026, 9, 30)
    assert tender.posted_date == date(2026, 8, 5)


def test_undp_drops_the_beirut_row(outcomes):
    assert not [t for t in outcomes["undp"].tenders if "Beirut" in t.title]


# ----------------------------------------------------------------------- SRTF
def test_srtf_maps_value_and_deadline(outcomes):
    tender = titled(outcomes["srtf"], "water pumps")
    assert tender.closing_date == date(2026, 9, 28)
    assert tender.estimated_value_usd == 1_250_000.0
    assert tender.url.endswith("/procurements/2026/water-idlib-001")


def test_srtf_drops_the_berlin_secretariat_row(outcomes):
    assert not [t for t in outcomes["srtf"].tenders if "Berlin" in t.title]


# ------------------------------------------------------------------------ GIZ
def test_giz_parses_german_dates(outcomes):
    assert titled(outcomes["giz"], "Wasserversorgung Aleppo").closing_date == date(2026, 12, 31)
    assert titled(outcomes["giz"], "Energieversorgung Homs").closing_date == date(2027, 1, 15)


def test_giz_reads_european_number_format(outcomes):
    """EUR 1.500.000 is 1.5 million, not 1.5 -- and it is not converted to USD."""
    tender = titled(outcomes["giz"], "Wasserversorgung Aleppo")
    assert tender.raw_currency == "EUR"
    assert tender.estimated_value_usd is None
    assert any("1500000" in f.replace(",", "") for f in tender.flags), tender.flags


def test_giz_unclosed_cell_does_not_put_the_title_in_the_deadline(outcomes):
    tender = titled(outcomes["giz"], "Studie zur Kooperation")
    assert tender.closing_date is None          # "n.v." is not a date
    assert "deadline_not_published" in tender.flags


def test_giz_drops_the_tunisia_row(outcomes):
    assert not [t for t in outcomes["giz"].tenders if "Tunesien" in t.title]


# ----------------------------------------------------------------------- IsDB
def test_isdb_maps_a_gpn_as_pipeline_not_biddable(outcomes):
    tender = titled(outcomes["isdb"], "General Procurement Notice")
    assert tender.is_pipeline, "a GPN is early intelligence, not something to bid on"
    assert tender.closing_date == date(2026, 11, 30)


def test_isdb_drops_the_uzbekistan_row(outcomes):
    assert not [t for t in outcomes["isdb"].tenders if "Tashkent" in t.title]


# ----------------------------------------------------------------------- GTAI
def test_gtai_carries_kfw_notices(outcomes):
    tender = titled(outcomes["gtai"], "water supply rehabilitation")
    assert "KfW" in tender.title
    assert tender.closing_date == date(2026, 10, 10)
    assert tender.url.startswith("https://www.gtai.de/en/trade/")


def test_gtai_drops_the_morocco_row(outcomes):
    assert not [t for t in outcomes["gtai"].tenders if "Casablanca" in t.title]


# ------------------------------------------------------------- shared invariant
@pytest.mark.parametrize("name", HTML_PORTALS)
def test_html_portals_do_not_fabricate_links(name, outcomes):
    for tender in outcomes[name].tenders:
        assert not tender.url.endswith("None")
        assert " " not in tender.url
