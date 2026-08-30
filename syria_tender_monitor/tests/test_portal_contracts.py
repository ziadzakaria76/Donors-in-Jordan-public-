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


def test_ted_reports_what_the_server_said_not_a_guess(profile, gate):
    """A rejection must carry TED's own explanation.

    This used to append "(limit must be <= 100)" to every non-OK response,
    while PAGE_LIMIT had been 100 all along -- so the message was false, and a
    live run lost the whole portal to it: readers are sent to a setting that is
    already correct.

    The response body is where a v3 rejection names the offending field, and it
    was being discarded.
    """
    from syria_monitor.portals.ted import TedPortal, PAGE_LIMIT

    class Stub(TedPortal):
        def __init__(self):
            self.profile, self.cfg = profile, {}

    class Response:
        def __init__(self, status, text):
            self.status, self.text, self.ok = status, text, False

    message = Stub()._rejection(
        Response(400, '{"message":"Invalid field name: buyer-country"}'), 1)

    assert "Invalid field name" in message, "TED's own words must survive"
    assert "400" in message
    assert "limit must be" not in message, "no hardcoded cause"
    assert PAGE_LIMIT == 100

    # An absent body must read as absent, not as a diagnosis.
    empty = Stub()._rejection(Response(500, ""), 2)
    assert "empty response body" in empty

    # A secret-shaped body is redacted before it reaches a log.
    leaky = Stub()._rejection(Response(401, "search?apiKey=SECRET123 rejected"), 1)
    assert "SECRET123" not in leaky and "<redacted>" in leaky

    # An error page can be a whole HTML document.
    assert len(Stub()._rejection(Response(400, "<html>" + "x" * 5000), 1)) < 600


# The opening of the reply TED actually sent on 2026-08-30 is verbatim from the
# run log; only the first 400 characters of the real list were ever printed, so
# the tail here is the shipped field names appended on the evidence that the
# sibling Jordan monitor sends exactly these and gets HTTP 200 in production.
#
# WHAT THIS THEREFORE PROVES, and what it does not: it pins the parser, and it
# fails the moment an unverified name is added to FIELDS -- which is the
# regression that took the portal down. It is NOT independent proof that TED
# accepts these ten; only a live run is that.
_TED_400_BODY = (
    '{"message":"Parameter \'fields\' contains unsupported value '
    '(supported values are: sme-part,touchpoint-gateway-ted-esen,submission-url-lot,'
    'publication-number,notice-title,publication-date,deadline-receipt-tender-date-lot,'
    'notice-type,total-value,buyer-name,links,description-lot,'
    'place-of-performance-country-lot,BT-13(t)-Part,BT-821-Lot)"}'
)


def test_ted_requests_only_fields_ted_supports():
    """Every requested name appears in TED's own supported list.

    An unsupported name is not a missing column -- it is HTTP 400 on page 1 and
    the entire portal reported down, which is how it behaved on every live run
    until the reply was printed.
    """
    from syria_monitor.portals.ted import FIELDS, _unsupported_fields_note

    note = _unsupported_fields_note(_TED_400_BODY)
    assert note.startswith("Every field"), (
        f"the shipped field list must be a subset of TED's own: {note}")
    assert len(FIELDS) == len(set(FIELDS)), "no duplicate field names"


def test_ted_rejection_names_the_offending_field():
    """The 400 excerpt truncates thousands of names before reaching the answer,
    so the comparison is made for the reader rather than left to them."""
    import syria_monitor.portals.ted as ted

    note = ted._unsupported_fields_note(_TED_400_BODY.replace(
        "deadline-receipt-tender-date-lot,", ""))
    assert "deadline-receipt-tender-date-lot" in note, note
    assert "Fields TED does not support" in note


def test_ted_field_note_is_silent_when_fields_are_not_the_problem():
    from syria_monitor.portals.ted import _unsupported_fields_note

    assert _unsupported_fields_note('{"message":"Rate limit exceeded"}') == ""
    assert _unsupported_fields_note("") == ""


def test_ted_reads_the_country_city_title_form():
    """TED's commoner title shape, which never matched.

    The pattern required whitespace after the separator, and in
    "Belgium-Brussels" the hyphen is followed by a letter -- so every
    Country-City notice reached the gate carrying no country and was judged on
    its text. For a full-text search on "syria" that is a search returning
    EU-wide notices that mention Syria and a check that cannot reject any of
    them. This title is verbatim from the report of 2026-08-30, where it ranked
    third and was filed as inside_syria.
    """
    from syria_monitor.portals.ted import TedPortal

    latvian = ("Beļģija-Brisele: Ārējā uzraudzība un izvērtēšana Eiropas "
               "Savienības ārējās darbības instrumentiem")
    assert TedPortal.country_from_title(latvian) == "Beļģija"
    assert TedPortal.country_from_title(
        "Belgium-Brussels: External monitoring of EU external action") == "Belgium"
    # The " - " form still works and is what the previous pattern covered.
    assert TedPortal.country_from_title(
        "Austria – License management software development services") == "Austria"
    assert TedPortal.country_from_title("Syria - Electricity Emergency Project") == "Syria"


def test_ted_makes_no_country_claim_it_cannot_check():
    """This prefix is used to REJECT, so a wrong reading discards real work.

    Three ways it can be wrong, and all three now abstain rather than guess:
    a sentence fragment that happens to contain a dash, a multi-word country in
    the Country-City form, and a script with no capitals to check. Abstaining
    costs nothing -- the record falls through to the text check.
    """
    from syria_monitor.portals.ted import TedPortal

    # Pre-existing: the " - " form claimed this as a country.
    assert TedPortal.country_from_title("Supply of equipment - Lot 3") is None
    assert TedPortal.country_from_title("United Kingdom-London: Technical assistance") is None
    # Arabic has no capitals. Exempting it read "supply of equipment, lot 3" as
    # a country and would have dropped the tender.
    assert TedPortal.country_from_title("توريد معدات - الحصة 3") is None
    assert TedPortal.country_from_title("Rehabilitation of water networks in Aleppo") is None


def test_a_magnitude_must_end_where_it_matches():
    """"Multiple" is not a million.

    The run of 2026-08-30 reported three UNGM notices at US$ 947,000,000,
    946,000,000 and 830,000,000, and they took the top three places in the
    report BECAUSE of it -- value feeds the score. The figures came from UNGM's
    own row text, where a reference number is followed by the country cell:

        ... UNICEF-2026-000946 Multiple destinations   ->  946 M

    `mn?` matched the M of "Multiple" with nothing requiring the token to end,
    and M means a million. "Ministry", "Metric" and "Mr" did it too.

    This is the second bug today caused by that same label; the first read it
    as a country.
    """
    from syria_monitor.money import parse_value

    for text in ("Request for proposal UNICEF-2026-000946 Multiple destinations",
                 "RFP-830 Multiple destinations",
                 "Ref 500 Ministry of Health",
                 "Lot 12 Metric tonnes of flour"):
        assert parse_value(text).amount is None, f"invented a value from {text!r}"


def test_real_magnitudes_still_parse():
    """The guard must not cost the values it exists to protect."""
    from syria_monitor.money import parse_value

    assert parse_value("Contract value USD 2.5 million").amount == 2_500_000
    assert parse_value("Budget: $3 M").amount == 3_000_000
    assert parse_value("Estimated 750 k").amount == 750_000
    assert parse_value("Total 1.2 bn USD").amount == 1_200_000_000
    # European thousands separators: 1.500.000 is 1.5 million, not 1.5.
    assert parse_value("EUR 1.500.000").amount == 1_500_000
    # Arabic, where the lookahead also must not reject a legitimate suffix.
    assert parse_value("قيمة العقد 5 مليون دولار").amount == 5_000_000


def test_the_uk_list_is_not_pointed_at_the_retired_consolidated_list():
    """The obvious replacement is the wrong one.

    data.gov.uk/dataset/financialsanctions IS the OFSI Consolidated List -- the
    list that closed on 28 January 2026. Pointing there would swap a loud 404
    for a list frozen since January that looks like it is working, which is
    strictly worse than the failure it replaces.

    The GOV.UK publication page is also out: resolving the link off it was
    shipped and run, and the page carries one asset link, a schema rather than
    the data, because the attachment list is client-rendered.
    """
    from syria_monitor.screening import SOURCES

    urls = " ".join(SOURCES["uk_sanctions"]["urls"])
    assert "data.gov.uk" not in urls, "that dataset is the retired list"
    assert "assets.publishing.service.gov.uk" not in urls, "content-addressed; rehashed weekly"
    assert all(u.startswith("https://sanctionslist.fcdo.gov.uk/") for u in
               SOURCES["uk_sanctions"]["urls"]), urls


def test_a_list_published_at_several_addresses_falls_through_to_a_working_one(tmp_path):
    from types import SimpleNamespace
    from syria_monitor.screening import Screener, SOURCES

    csv_url, xml_url = SOURCES["uk_sanctions"]["urls"]
    xml = ('<?xml version="1.0"?><Designations>'
           '<Designation><Names><Name1>Ahmad Example</Name1></Names></Designation>'
           '<Designation><Names><Name1>Example Trading LLC</Name1></Names></Designation>'
           '</Designations>')

    class CsvGone:
        def __init__(self): self.asked = []
        def get(self, url, **kw):
            self.asked.append(url)
            if url == csv_url:
                return SimpleNamespace(text="Not Found", status=404, ok=False)
            return SimpleNamespace(text=xml, status=200, ok=True)

    fetcher = CsvGone()
    result = Screener(cache_dir=tmp_path, fetcher=fetcher).refresh("uk_sanctions")

    assert fetcher.asked == [csv_url, xml_url], "tries each address in turn"
    assert result.source_url == xml_url, "records WHICH address served it"
    # Normalised, as the CSV path normalises -- screening compares normalised
    # forms, so raw names would load, report a plausible count, and match nothing.
    assert result.names == {"ahmad example", "example trading llc"}


def test_every_address_failing_names_every_address(tmp_path):
    """"0 names" cannot distinguish a moved file from an empty one from a
    parser that did not understand the format. This module has produced all
    three today."""
    from types import SimpleNamespace
    from syria_monitor.screening import Screener, ScreeningUnavailable

    class AllGone:
        def get(self, url, **kw):
            return SimpleNamespace(text="Not Found", status=404, ok=False)

    try:
        Screener(cache_dir=tmp_path, fetcher=AllGone()).refresh("uk_sanctions")
    except ScreeningUnavailable as exc:
        message = str(exc)
        assert "UK-Sanctions-List.csv" in message and "UK-Sanctions-List.xml" in message
        assert "404" in message
    else:
        raise AssertionError("must raise rather than return an empty list")


def test_xml_name_tags_do_not_swallow_their_own_metadata():
    """A tag merely CONTAINING "name" also catches NameType, and padding the
    list with words like "Primary name" turns every run into a false flag."""
    from syria_monitor.screening import parse_xml_names

    xml = ('<Designations><Designation><Names><Name>'
           '<NameType>Primary name</NameType>'
           '<Name1>Ahmad Example</Name1>'
           '<NameStatus>Active</NameStatus>'
           '</Name></Names></Designation></Designations>')
    names = parse_xml_names(xml)
    assert "ahmad example" in names
    assert "primary name" not in names and "active" not in names, names


def test_a_document_that_is_not_xml_still_parses_as_csv():
    """The document decides how it is read, not the configuration."""
    from syria_monitor.screening import parse_names

    csv_text = "Name,Regime\nAhmad Example,Syria\nExample Trading LLC,Syria\n"
    names = parse_names(csv_text, {"format": "csv", "name_column": None})
    assert "ahmad example" in names and "example trading llc" in names


# --------------------------------------------------------------- the app's view
#
# The Android app is a separate codebase in another language, and the only thing
# joining them is a JSON document. Nothing in Python fails when a field it needs
# stops being written -- the failure appears as a blank line on a phone, days
# later, with no error anywhere. So the contract is asserted against the app's
# OWN SOURCE rather than against a copy of it kept here, which would drift.

def _app_report_kt() -> str:
    from pathlib import Path
    kt = (Path(__file__).resolve().parents[2] / "android" / "app" / "src" / "main"
          / "java" / "jo" / "tendermonitor" / "data" / "report" / "Report.kt")
    return kt.read_text(encoding="utf-8")


def _declared_fields(kotlin: str, data_class: str) -> set[str]:
    """The JSON keys one @Serializable data class expects."""
    import re
    body = re.search(rf"data class {data_class}\((.*?)\n\)", kotlin, re.S).group(1)
    named = set(re.findall(r'@SerialName\("([^"]+)"\)', body))
    plain = set()
    for line in body.splitlines():
        m = re.match(r"\s*val (\w+):", line)
        if m and "@SerialName" not in line:
            plain.add(m.group(1))
    return named | plain


def _sample_run():
    from datetime import date
    from syria_monitor.models import Tender
    from syria_monitor.portals.base import PortalOutcome
    from syria_monitor.gate import GateStats
    from syria_monitor.pipeline import RunResult

    tender = Tender(id="x1", title="Rehabilitation of clinics, Aleppo", portal="ungm",
                    url="https://www.ungm.org/1", score=79.5, sector="Health",
                    notice_type="Invitation to bid", language="en",
                    posted_date=date(2026, 8, 12), closing_date=date(2026, 9, 8),
                    contact="UNDP", description="Works",
                    delivery_country="Syrian Arab Republic")
    read = PortalOutcome(name="ungm", label="UNGM", url="https://www.ungm.org",
                         tenders=[tender], available=True, layer="selectors",
                         quality=0.91)
    read.stats = GateStats(); read.stats.seen = 87
    broken = PortalOutcome(name="ted", label="EU TED", url="https://ted.example",
                           available=False, error="HTTP 400")
    broken.stats = GateStats()
    skipped = PortalOutcome(name="samgov", label="SAM.gov", url="https://sam.example",
                            skipped_reason="SAM_API_KEY not set")
    skipped.stats = GateStats()

    result = RunResult(started="2026-08-30T05:00:00")
    result.tenders = [tender]
    result.portals = [read, broken, skipped]
    result.duplicates_collapsed = 11
    result.expired_dropped = 3
    return result


def _write_sample(tmp_path):
    import json
    from datetime import date
    from syria_monitor.report.app_json_writer import write_app_json
    out = write_app_json(_sample_run(), tmp_path / "app.json",
                         {"name": "Syria", "key": "syria"}, today=date(2026, 8, 30))
    return json.loads(out.read_text(encoding="utf-8"))


def test_the_app_can_read_every_field_it_declares(tmp_path):
    """Asserted against Report.kt itself, so adding a field there fails here.

    A field the app expects and this never writes does not raise: kotlinx fills
    the default and the phone shows an empty line, which looks like a quiet day
    rather than a broken contract.
    """
    kotlin = _app_report_kt()
    document = _write_sample(tmp_path)

    for data_class, got in (("Report", document),
                            ("RunSummary", document["run"]),
                            ("Opportunity", document["tenders"][0]),
                            ("PortalStatus", document["portals"][0])):
        missing = sorted(f for f in _declared_fields(kotlin, data_class) if f not in got)
        assert not missing, f"{data_class} expects fields we never write: {missing}"


def test_the_schema_constant_matches_the_app(tmp_path):
    """The app refuses a schema it was not written for -- deliberately, since
    half-parsed fields are worse than a sentence saying the app is out of date.
    A mismatch here is a blank screen on every phone."""
    import re
    from syria_monitor.report.app_json_writer import REPORT_SCHEMA

    supported = int(re.search(r"SUPPORTED_SCHEMA\s*=\s*(\d+)", _app_report_kt()).group(1))
    assert REPORT_SCHEMA == supported, (
        f"we write schema {REPORT_SCHEMA}, the app renders only {supported}")
    assert _write_sample(tmp_path)["schema"] == supported


def test_scanned_is_null_when_a_portal_never_filtered(tmp_path):
    """Null is not zero, and the difference is the whole point of the field.

    "Read nothing" and "read five hundred and none were relevant" are the two
    diagnoses it separates. A portal that was skipped or unavailable never
    reached its filter, so it must report null rather than the 0 its stats hold.
    """
    portals = {p["key"]: p for p in _write_sample(tmp_path)["portals"]}
    assert portals["ungm"]["scanned"] == 87
    assert portals["ted"]["scanned"] is None, "unavailable: never filtered"
    assert portals["samgov"]["scanned"] is None, "skipped: never filtered"


def test_portal_status_uses_the_apps_vocabulary(tmp_path):
    """The app tests `status == "unavailable"` to colour a portal broken, so a
    word it does not know renders as healthy. A skipped portal is Jordan's
    "unconfigured" -- SAM.gov without its key is exactly that -- rather than a
    fifth status the app cannot show."""
    portals = {p["key"]: p for p in _write_sample(tmp_path)["portals"]}
    assert portals["ungm"]["status"] == "ok"
    assert portals["ted"]["status"] == "unavailable"
    assert portals["samgov"]["status"] == "unconfigured"


def test_the_run_summary_counts_only_portals_that_could_have_worked(tmp_path):
    """A skipped portal is not a broken one: counting SAM.gov as broken because
    it has no key would put a permanent red line in every report."""
    run = _write_sample(tmp_path)["run"]
    assert run["portals_total"] == 2, "the skipped portal is not considered"
    assert run["portals_ok"] == 1 and run["portals_broken"] == 1
    assert run["status"] == "partial", "some broken, not all"
    assert run["merged_duplicates"] == 11
    assert run["dropped"] == {"expired": 3}


def test_days_left_is_computed_and_null_when_there_is_no_deadline(tmp_path):
    from datetime import date
    from syria_monitor.report.app_json_writer import write_app_json

    document = _write_sample(tmp_path)
    assert document["tenders"][0]["days_left"] == 9, "08-Sep is nine days after 30-Aug"

    run = _sample_run()
    run.tenders[0].closing_date = None
    out = write_app_json(run, tmp_path / "b.json", {"name": "Syria"},
                         today=date(2026, 8, 30))
    import json
    assert json.loads(out.read_text())["tenders"][0]["days_left"] is None
