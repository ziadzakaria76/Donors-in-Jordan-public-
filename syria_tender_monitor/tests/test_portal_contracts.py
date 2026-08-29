"""Contract tests for the four REST portals.

Each portal is fed a payload in the shape its API is documented to return, and
the field mapping is asserted end to end: title, dates, value, link, country
field, and the gate's verdict.

IMPORTANT: the payloads under tests/fixtures/api/ are RECONSTRUCTIONS. No live
API was reachable from the environment this was written in, so these encode
what the parsers assume, not what the APIs were observed to send. They exist so
that a wrong assumption fails here rather than silently on first live contact --
and so that replacing a file with a real capture immediately shows what differs.
Provenance is recorded in tests/fixtures/api/README.md.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from syria_monitor.fetch import Fetcher, Response
from syria_monitor.portals import REGISTRY

API_FIXTURES = Path(__file__).parent / "fixtures" / "api"


def payload(name: str) -> dict:
    return json.loads((API_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class StubFetcher(Fetcher):
    """Serves queued payloads; the last one repeats."""

    def __init__(self, *payloads):
        super().__init__()
        self.queue = list(payloads)
        self.calls: list[tuple[str, dict]] = []

    def _next(self):
        return self.queue.pop(0) if len(self.queue) > 1 else self.queue[0]

    def json(self, url, **kwargs):
        self.calls.append((url, kwargs.get("params") or {}))
        return self._next()

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs.get("json") or {}))
        return Response(url=url, status=200, text=json.dumps(self._next()), headers={})

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs.get("params") or {}))
        return Response(url=url, status=200, text=json.dumps(self._next()), headers={})


def collect(name, fetcher, profile, gate, cfg=None):
    return REGISTRY[name](cfg or {}, profile, fetcher, gate).collect()


def by_title(outcome, fragment):
    matches = [t for t in outcome.tenders if fragment.lower() in t.title.lower()]
    assert matches, f"no kept tender matching {fragment!r}: {[t.title for t in outcome.tenders]}"
    return matches[0]


# ----------------------------------------------------------------- World Bank
@pytest.fixture
def worldbank(profile, gate):
    return collect("worldbank", StubFetcher(payload("worldbank")), profile, gate)


def test_worldbank_maps_its_fields(worldbank):
    tender = by_title(worldbank, "public financial management")
    assert tender.id == "OP00460737"
    assert tender.posted_date == date(2026, 8, 1)
    assert tender.closing_date == date(2026, 9, 30)
    assert tender.notice_type == "Request for Expression of Interest"
    assert tender.sector == "Public Administration"
    assert tender.contact == "procurement@mof.gov.sy"
    assert tender.estimated_value_usd == 2_400_000.0
    assert tender.syria_link_type == "inside_syria"


def test_worldbank_builds_a_link_only_from_a_notice_id(worldbank):
    assert by_title(worldbank, "public financial management").url == (
        "https://projects.worldbank.org/en/projects-operations/procurement-detail/OP00460737")
    # The third record's id is a PROJECT id (P175447): no link beats a 404 link.
    assert by_title(worldbank, "laboratory equipment").url is None


def test_worldbank_rejects_the_foreign_record_despite_the_indexed_body(worldbank):
    """The Malawi record's notice_text says "Syria" twice -- qterm matched on it."""
    assert not [t for t in worldbank.tenders if "Malawi" in (t.title + (t.description or ""))]
    assert worldbank.stats.rejected_by_field == 1
    assert worldbank.stats.seen == 3


def test_worldbank_keeps_a_notice_whose_title_names_no_country(worldbank):
    assert by_title(worldbank, "laboratory equipment").syria_link_type == "inside_syria"


def test_worldbank_never_sends_the_ignored_country_parameter(profile, gate):
    fetcher = StubFetcher(payload("worldbank"))
    collect("worldbank", fetcher, profile, gate)
    sent = fetcher.calls[0][1]
    for ignored in ("countryshortname", "country", "countrycode", "cty"):
        assert ignored not in sent, f"{ignored} is silently ignored by the API -- do not send it"
    assert sent["qterm"]


# ------------------------------------------------------------------------ TED
@pytest.fixture
def ted(profile, gate):
    return collect("ted", StubFetcher(payload("ted")), profile, gate)


def test_ted_flattens_multilingual_maps(ted):
    tender = by_title(ted, "rehabilitation of water distribution")
    assert tender.title.startswith("Syria - Rehabilitation")
    assert tender.url == "https://ted.europa.eu/en/notice/-/detail/512345-2026"
    assert tender.closing_date == date(2026, 9, 30)
    assert tender.posted_date == date(2026, 8, 10)


def test_ted_uses_place_of_performance_as_delivery_not_buyer_country(ted):
    tender = by_title(ted, "rehabilitation of water distribution")
    assert tender.delivery_country == "SY"          # place-of-performance SYR
    assert tender.syria_link_type == "inside_syria"  # not "cross-border" via buyer DEU


def test_ted_labels_a_jordan_delivered_refugee_tender_rather_than_dropping_it(ted):
    """TED reports countries as ISO3, so JOR has to resolve to Jordan.

    Matching only ISO2 left this record "unclassified" -- excluded either way,
    but invisible in the split that exists to show what is being excluded.
    """
    mafraq = [t for t in ted.tenders if "Mafraq" in t.title]
    assert mafraq, "the record must be kept and labelled, not silently dropped"
    assert mafraq[0].syria_link_type == "refugee_hosting_only"
    assert mafraq[0].delivery_country == "JO"
    assert ted.stats.link_types.get("refugee_hosting_only") == 1


def test_ted_refugee_tender_is_then_excluded_by_the_pipeline_scope_filter(config, profile,
                                                                          monkeypatch):
    """Portals keep related records; the pipeline decides what is in scope."""
    from syria_monitor.pipeline import run as run_pipeline
    from syria_monitor.portals import REGISTRY

    stub = StubFetcher(payload("ted"))

    class FixtureTed(REGISTRY["ted"]):
        def __init__(self, cfg, prof, fetcher, gate):
            super().__init__(cfg, prof, stub, gate)

    monkeypatch.setitem(REGISTRY, "ted", FixtureTed)
    result = run_pipeline(config, fetcher=stub, today=date(2026, 8, 23), portals=["ted"])

    assert not any("Mafraq" in t.title for t in result.tenders)
    assert any("Mafraq" in t.title for t in result.excluded)
    assert result.counts["refugee_hosting_only"] == 1


def test_ted_reads_the_non_lot_place_of_performance_field_too(ted):
    """The third record uses place-of-performance-country, not ...-country-lot."""
    assert by_title(ted, "laboratory equipment").syria_link_type == "inside_syria"


def test_ted_never_requests_more_than_the_page_limit(profile, gate):
    fetcher = StubFetcher(payload("ted"))
    collect("ted", fetcher, profile, gate)
    assert fetcher.calls[0][1]["limit"] <= 100      # 250 is a silent HTTP 400


# -------------------------------------------------------------------- SAM.gov
@pytest.fixture
def samgov(profile, gate, monkeypatch):
    monkeypatch.setenv("SAM_API_KEY", "test-key")
    return collect("samgov", StubFetcher(payload("samgov")), profile, gate)


def test_samgov_maps_its_fields(samgov):
    tender = by_title(samgov, "health system recovery")
    assert tender.id == "a1b2c3d4e5f60718293a4b5c6d7e8f90"
    assert tender.url == "https://sam.gov/opp/a1b2c3d4e5f60718293a4b5c6d7e8f90/view"
    assert tender.posted_date == date(2026, 8, 5)
    assert tender.closing_date == date(2026, 9, 25)     # offset-bearing timestamp
    assert tender.eligibility == "Total Small Business Set-Aside"
    assert tender.contact == "grants@state.gov"


def test_samgov_reads_ncode_from_place_of_performance(samgov):
    assert by_title(samgov, "health system recovery").delivery_country == "SY"


def test_samgov_rejects_damascus_maryland(samgov):
    """SAM.gov scans a whole national corpus, so a bare place-name match pulls in
    US municipal contracts."""
    assert not [t for t in samgov.tenders if "Maryland" in t.title]
    assert samgov.stats.rejected_by_field == 1


def test_samgov_description_is_a_url_and_never_feeds_the_country_check(samgov):
    tender = by_title(samgov, "health system recovery")
    assert tender.description.startswith("https://api.sam.gov/")


def test_samgov_sends_a_range_the_api_will_accept(profile, gate, monkeypatch):
    from datetime import datetime
    monkeypatch.setenv("SAM_API_KEY", "test-key")
    fetcher = StubFetcher(payload("samgov"))
    collect("samgov", fetcher, profile, gate)
    params = fetcher.calls[0][1]
    start = datetime.strptime(params["postedFrom"], "%m/%d/%Y")
    end = datetime.strptime(params["postedTo"], "%m/%d/%Y")
    assert 0 < (end - start).days <= 365, "the API rejects any range over a year"
    assert params["ncode"] == "SY"


# ----------------------------------------------------------- UK Find a Tender
@pytest.fixture
def uk_fts(profile, gate):
    second_page = {"releases": [], "links": {}}
    return collect("uk_fts", StubFetcher(payload("uk_fts"), second_page), profile, gate)


def test_uk_fts_maps_its_fields(uk_fts):
    tender = by_title(uk_fts, "monitoring and evaluation")
    assert tender.id == "ocds-h6vhtk-04a5b1"
    assert tender.url == "https://www.find-tender.service.gov.uk/Notice/012345-2026"
    assert tender.closing_date == date(2026, 9, 18)
    assert tender.eligibility == "Open to suppliers of any nationality."
    assert tender.syria_link_type == "inside_syria"


def test_uk_fts_reads_the_buyer_from_parties_by_role(uk_fts):
    """Buyer and supplier live in parties[] selected by role, not at top level."""
    assert by_title(uk_fts, "monitoring and evaluation").contact == "procurement@fcdo.gov.uk"


def test_uk_fts_value_is_reported_but_not_converted_to_usd(uk_fts):
    tender = by_title(uk_fts, "monitoring and evaluation")
    assert tender.raw_currency == "GBP"
    assert tender.estimated_value_usd is None


def test_uk_fts_rejects_the_assyrian_heritage_record(uk_fts):
    """"Assyrian" and "Syriac" in an Iraq-delivered tender: the classic false
    positive a substring match would keep."""
    assert not [t for t in uk_fts.tenders if "Assyrian" in t.title]
    assert uk_fts.stats.seen == 2


def test_uk_fts_sends_the_documented_date_format(profile, gate):
    fetcher = StubFetcher(payload("uk_fts"), {"releases": [], "links": {}})
    collect("uk_fts", fetcher, profile, gate)
    updated_from = fetcher.calls[0][1]["updatedFrom"]
    assert updated_from.endswith("T00:00:00") and len(updated_from) == 19
    assert fetcher.calls[0][1]["limit"] == 100


def test_uk_fts_pagination_stops_and_does_not_loop(profile, gate):
    """The next-link chain can loop; the seen-set is what terminates it."""
    looping = StubFetcher(payload("uk_fts"))          # same page, same next link, forever
    outcome = collect("uk_fts", looping, profile, gate)
    assert len(looping.calls) <= 3
    assert outcome.available is True


# --------------------------------------------------------------- shared rules
@pytest.mark.parametrize("name,fixture_name,extra_env", [
    ("worldbank", "worldbank", None),
    ("ted", "ted", None),
    ("samgov", "samgov", "SAM_API_KEY"),
    ("uk_fts", "uk_fts", None),
])
def test_every_rest_portal_drops_at_least_one_foreign_record(name, fixture_name, extra_env,
                                                             profile, gate, monkeypatch):
    """Each fixture carries a record for another country. No portal may ship it,
    whatever its own API claims to have filtered."""
    if extra_env:
        monkeypatch.setenv(extra_env, "test-key")
    outcome = collect(name, StubFetcher(payload(fixture_name), {"releases": [], "links": {}}),
                      profile, gate)
    assert outcome.stats.seen > len(outcome.tenders), (
        f"{name} kept every record it fetched -- the country gate did nothing")
    assert outcome.stats.rejected_by_field >= 1


@pytest.mark.parametrize("name,fixture_name,extra_env", [
    ("worldbank", "worldbank", None),
    ("ted", "ted", None),
    ("samgov", "samgov", "SAM_API_KEY"),
    ("uk_fts", "uk_fts", None),
])
def test_every_kept_record_has_the_fields_the_report_needs(name, fixture_name, extra_env,
                                                           profile, gate, monkeypatch):
    if extra_env:
        monkeypatch.setenv(extra_env, "test-key")
    outcome = collect(name, StubFetcher(payload(fixture_name), {"releases": [], "links": {}}),
                      profile, gate)
    for tender in outcome.tenders:
        assert tender.id and tender.title, f"{name}: record missing id or title"
        assert tender.portal == name
        assert tender.syria_link_type in ("inside_syria", "cross_border_hub",
                                          "regional_crisis", "refugee_hosting_only")
        assert tender.language in ("en", "ar")
