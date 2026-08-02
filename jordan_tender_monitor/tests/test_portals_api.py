"""
Tests for the four REST-API portal modules.

These had no coverage at all: their response-parsing had literally never been
executed, because the APIs are unreachable from the build environment. Feeding
them synthetic payloads in the documented shapes exercises every line that
turns a response into a record, and pins down what happens when a response is
empty, malformed, or a shape the module did not expect.

This does NOT verify the modules against the real APIs. The payloads here are
what the documentation says the responses look like; if an API returns
something different, these tests will still pass and the portal will still
fail. What they do prove is that the parsing logic is correct GIVEN the shape,
and that a surprising shape produces a diagnosed PortalError rather than a
crash or a silent empty result.
"""

from __future__ import annotations

from datetime import date

from jordan_tender_monitor import config
from jordan_tender_monitor.portals import base, fcdo, samgov, ted, worldbank
from jordan_tender_monitor.portals.base import PortalError

from .harness import check, check_eq


class _Stub:
    """Swaps base.fetch_json / base.post_json for a canned response."""

    def __init__(self, payload, expect_calls: int | None = None):
        self.payload = payload
        self.calls: list[tuple] = []
        self._orig_get = base.fetch_json
        self._orig_post = base.post_json

    def __enter__(self):
        def fake_get(url, **kwargs):
            self.calls.append((url, kwargs))
            value = self.payload
            if callable(value):
                return value(url, **kwargs)
            return value

        def fake_post(url, payload, **kwargs):
            self.calls.append((url, payload))
            value = self.payload
            if callable(value):
                return value(url, payload=payload, **kwargs)
            return value

        base.fetch_json = fake_get
        base.post_json = fake_post
        # The portal modules imported `base`, not the functions, so patching
        # the module attribute is enough.
        return self

    def __exit__(self, *exc):
        base.fetch_json = self._orig_get
        base.post_json = self._orig_post
        return False


# ---------------------------------------------------------------------------
# World Bank
# ---------------------------------------------------------------------------

_WB = {"procnotices": [
    {"id": "OP00291234",
     "project_name": "Jordan Public Financial Management Reform",
     "bid_description": "Consulting services for treasury modernisation in Amman.",
     "noticedate": "2026-06-01T00:00:00Z",
     "submission_deadline_date": "2026-09-15T00:00:00Z",
     "contract_value": "USD 1,850,000",
     "notice_type": "Request for Expression of Interest",
     "url": "https://projects.worldbank.org/notice/OP00291234",
     "contact_email": "procurement@mof.gov.jo"},
    {"id": "OP00291235",
     "project_name": "Jordan Water Sector Efficiency",
     "bid_description": "Supervision consultancy, Irbid governorate.",
     "noticedate": "2026-06-05T00:00:00Z",
     "submission_deadline_date": "2026-10-01T00:00:00Z",
     "notice_type": "General Procurement Notice",
     "url": "https://projects.worldbank.org/notice/OP00291235"},
]}


def test_worldbank_parses_documented_shape():
    with _Stub(_WB):
        records = worldbank.fetch_tenders()
    check_eq(len(records), 2, "worldbank: both notices parsed")
    r = records[0]
    check_eq(r["title"], "Jordan Public Financial Management Reform", "worldbank: title")
    check_eq(r["posted_date"], date(2026, 6, 1), "worldbank: posted date")
    check_eq(r["closing_date"], date(2026, 9, 15), "worldbank: closing date")
    check_eq(r["estimated_value_usd"], 1_850_000.0, "worldbank: value in USD")
    check_eq(r["portal"], "worldbank", "worldbank: portal tagged")
    check(r["url"].startswith("https://"), "worldbank: url carried through")
    check_eq(records[1]["estimated_value_usd"], None,
             "worldbank: an unpublished value stays None rather than becoming 0")


def test_worldbank_accepts_alternative_response_keys():
    """The API has used both a keyed dict and a flat list over the years."""
    with _Stub({"notices": _WB["procnotices"]}):
        check_eq(len(worldbank.fetch_tenders()), 2, "worldbank: 'notices' key accepted")
    with _Stub(list(_WB["procnotices"])):
        check_eq(len(worldbank.fetch_tenders()), 2, "worldbank: a bare list accepted")


def test_worldbank_empty_response_is_diagnosed_not_silent():
    """An empty response could be a changed shape; it must not read as 'no tenders'."""
    for payload in ({}, {"procnotices": []}, {"unexpected": "shape"}):
        try:
            worldbank_records = None
            with _Stub(payload):
                worldbank_records = worldbank.fetch_tenders()
            check(False, "worldbank: an unusable response must raise",
                  f"returned {worldbank_records!r} for {payload!r}")
        except PortalError as exc:
            check("response shape" in exc.reason or "no notices" in exc.reason,
                  "worldbank: the diagnosis names a possible shape change")


# ---------------------------------------------------------------------------
# EU TED
# ---------------------------------------------------------------------------

_TED = {"notices": [
    {"publication-number": "123456-2026",
     "notice-title": {"eng": ["Technical Assistance for Governance Reform, Jordan"]},
     "publication-date": "2026-06-10+02:00",
     "deadline-receipt-tender-date-lot": ["2026-09-20+02:00"],
     "notice-type": "cn-standard",
     "total-value": {"eng": ["EUR 2.400.000"]},
     "buyer-name": {"eng": ["European Commission"]},
     "description-lot": {"eng": ["Support to public administration reform in Amman."]},
     "links": {"html": "https://ted.europa.eu/en/notice/-/detail/123456-2026"}},
    {"publication-number": "123457-2026",
     "notice-title": {"eng": ["Road Resurfacing, Jordanstown, County Antrim"]},
     "publication-date": "2026-06-11+01:00",
     "notice-type": "cn-standard",
     "description-lot": {"eng": ["Civil works in Northern Ireland."]},
     "links": {"html": "https://ted.europa.eu/en/notice/-/detail/123457-2026"}},
]}


def test_ted_parses_multilingual_fields():
    with _Stub(_TED):
        records = ted.fetch_tenders()
    check_eq(len(records), 1,
             "ted: only the Jordan notice survives -- Jordanstown is excluded")
    r = records[0]
    check_eq(r["title"], "Technical Assistance for Governance Reform, Jordan",
             "ted: multilingual title unwrapped")
    check_eq(r["posted_date"], date(2026, 6, 10), "ted: publication date")
    check_eq(r["closing_date"], date(2026, 9, 20),
             "ted: deadline unwrapped from a list")
    check_eq(r["estimated_value_usd"], round(2_400_000 * config.FX_TO_USD["EUR"], 2),
             "ted: EUR 2.400.000 read as 2.4 million and converted")
    check_eq(r["contact"], "European Commission", "ted: buyer name unwrapped")
    check_eq(r["reference"], "123456-2026", "ted: publication number kept")


def test_ted_builds_a_url_when_links_are_missing():
    payload = {"notices": [{"publication-number": "999999-2026",
                            "notice-title": "Advisory Services, Amman, Jordan",
                            "publication-date": "2026-07-01",
                            "description-lot": "Consulting."}]}
    with _Stub(payload):
        records = ted.fetch_tenders()
    check_eq(len(records), 1, "ted: a notice with no links block still parses")
    check("999999-2026" in (records[0]["url"] or ""),
          "ted: a detail URL is constructed from the publication number")


def test_ted_empty_response_is_diagnosed():
    try:
        with _Stub({"notices": []}):
            ted.fetch_tenders()
        check(False, "ted: an empty response must raise")
    except PortalError as exc:
        check("query" in exc.reason, "ted: the diagnosis points at the v3 query grammar")


# ---------------------------------------------------------------------------
# SAM.gov
# ---------------------------------------------------------------------------

_SAM = {"opportunitiesData": [
    {"noticeId": "abc123",
     "title": "Institutional Support Services, Amman, Jordan",
     "postedDate": "2026-06-02",
     "responseDeadLine": "2026-09-30T17:00:00-04:00",
     "type": "Solicitation",
     "uiLink": "https://sam.gov/opp/abc123/view",
     "description": "USAID Jordan institutional support.",
     "award": {"amount": "1200000"},
     "pointOfContact": [{"fullName": "A Buyer", "email": "buyer@example.gov"}]},
    {"noticeId": "def456",
     "title": "Facilities Maintenance, Fort Bragg",
     "postedDate": "2026-06-03",
     "responseDeadLine": "2026-08-30T17:00:00-04:00",
     "type": "Solicitation",
     "uiLink": "https://sam.gov/opp/def456/view",
     "description": "Domestic US contract."},
]}


def test_samgov_requires_a_key_and_says_so():
    original = config.SAM_API_KEY
    try:
        config.SAM_API_KEY = ""
        try:
            samgov.fetch_tenders()
            check(False, "samgov: a missing key must raise")
        except PortalError as exc:
            check(exc.reason.startswith("not configured"),
                  "samgov: the reason starts with 'not configured'",
                  "so scraper.py classifies it as unconfigured, not broken")
            check("1-4 weeks" in exc.reason,
                  "samgov: the approval lead time is stated")
    finally:
        config.SAM_API_KEY = original


def test_samgov_parses_and_filters_to_jordan():
    original = config.SAM_API_KEY
    try:
        config.SAM_API_KEY = "test-key-not-a-real-secret"
        with _Stub(_SAM) as stub:
            records = samgov.fetch_tenders()
        check_eq(len(records), 1, "samgov: the domestic US notice is filtered out")
        r = records[0]
        check_eq(r["posted_date"], date(2026, 6, 2), "samgov: posted date")
        check_eq(r["closing_date"], date(2026, 9, 30), "samgov: response deadline")
        check_eq(r["estimated_value_usd"], 1_200_000.0,
                 "samgov: the award amount is read as a bare number")
        check("buyer@example.gov" in (r["contact"] or ""), "samgov: contact extracted")
        check(any("api_key" in str(c[1]) for c in stub.calls),
              "samgov: the key is sent as a request parameter")
    finally:
        config.SAM_API_KEY = original


def test_samgov_empty_window_is_normal_not_an_error():
    """Jordan genuinely has quiet months on SAM.gov."""
    original = config.SAM_API_KEY
    try:
        config.SAM_API_KEY = "test-key-not-a-real-secret"
        with _Stub({"opportunitiesData": []}):
            records = samgov.fetch_tenders()
        check_eq(records, [], "samgov: an empty window returns [] rather than raising")
    finally:
        config.SAM_API_KEY = original


# ---------------------------------------------------------------------------
# UK Find a Tender (OCDS)
# ---------------------------------------------------------------------------

def _ocds(next_url=None, releases=None):
    package = {"releases": releases if releases is not None else [
        {"ocid": "ocds-h6vhtk-04abcd",
         "date": "2026-06-01T09:00:00Z",
         "tag": ["tender"],
         "tender": {"title": "Governance Advisory Programme, Jordan",
                    "description": "FCDO-funded technical assistance in Amman.",
                    "mainProcurementCategory": "services",
                    "value": {"amount": 850000, "currency": "GBP"},
                    "tenderPeriod": {"endDate": "2026-09-12T12:00:00Z"},
                    "documents": [{"url": "https://find-tender.service.gov.uk/Notice/001"}]},
         "parties": [{"name": "Foreign, Commonwealth & Development Office",
                      "roles": ["buyer"]}]},
        {"ocid": "ocds-h6vhtk-04abce",
         "date": "2026-06-02T09:00:00Z",
         "tag": ["tender"],
         "tender": {"title": "Grounds Maintenance, Jordanstown Campus",
                    "description": "Landscaping services in County Antrim.",
                    "mainProcurementCategory": "services",
                    "tenderPeriod": {"endDate": "2026-09-14T12:00:00Z"}}},
    ]}
    if next_url:
        package["links"] = {"next": next_url}
    return package


def test_fcdo_parses_ocds_and_excludes_jordanstown():
    """The whole-UK corpus is why word-boundary country matching exists."""
    with _Stub(_ocds()):
        records = fcdo.fetch_tenders()
    check_eq(len(records), 1, "fcdo: Jordanstown is NOT matched as Jordan")
    r = records[0]
    check_eq(r["title"], "Governance Advisory Programme, Jordan", "fcdo: title")
    check_eq(r["posted_date"], date(2026, 6, 1), "fcdo: release date")
    check_eq(r["closing_date"], date(2026, 9, 12), "fcdo: tenderPeriod.endDate")
    check_eq(r["estimated_value_usd"], round(850_000 * config.FX_TO_USD["GBP"], 2),
             "fcdo: GBP value converted to USD")
    check_eq(r["notice_type"], "services", "fcdo: procurement category as notice type")
    check("Foreign" in (r["contact"] or ""), "fcdo: buyer party resolved")
    check_eq(r["reference"], "ocds-h6vhtk-04abcd", "fcdo: ocid kept as the reference")
    check("find-tender" in (r["url"] or ""), "fcdo: document URL used")


def test_fcdo_notice_type_survives_a_missing_tag():
    """The notice_type expression mixes `or` with a conditional -- pin it down."""
    releases = [{"ocid": "ocds-x", "date": "2026-06-01T09:00:00Z",
                 "tender": {"title": "Advisory Services, Amman, Jordan",
                            "mainProcurementCategory": "services",
                            "tenderPeriod": {"endDate": "2026-09-01T00:00:00Z"}}}]
    with _Stub(_ocds(releases=releases)):
        records = fcdo.fetch_tenders()
    check_eq(len(records), 1, "fcdo: a release with no tag still parses")
    check_eq(records[0]["notice_type"], "services",
             "fcdo: notice type is read with no tag present")

    releases[0]["tag"] = []
    with _Stub(_ocds(releases=releases)):
        records = fcdo.fetch_tenders()
    check_eq(len(records), 1, "fcdo: an EMPTY tag list does not raise IndexError")


def test_fcdo_pagination_terminates():
    """Cursor pagination must not loop when a page points back at itself."""
    seen = {"n": 0}

    def payload(url, **kwargs):
        seen["n"] += 1
        # Always advertises a next page: only the self-URL guard and the page
        # cap can stop this.
        return _ocds(next_url="https://find-tender.service.gov.uk/api/1.0/next")

    with _Stub(payload):
        records = fcdo.fetch_tenders()
    check(seen["n"] <= config.MAX_PAGINATION_PAGES + 1,
          "fcdo: pagination stops at the configured page cap",
          f"made {seen['n']} requests")
    check(records, "fcdo: records are still returned while paginating")


def test_fcdo_rejects_a_non_dict_response():
    try:
        with _Stub([1, 2, 3]):
            fcdo.fetch_tenders()
        check(False, "fcdo: a non-dict OCDS response must raise")
    except PortalError as exc:
        check("shape" in exc.reason, "fcdo: the diagnosis names the response shape")


def test_every_api_module_returns_the_standard_record():
    """Nothing downstream should care whether a portal was an API or a scrape."""
    original = config.SAM_API_KEY
    try:
        config.SAM_API_KEY = "test-key-not-a-real-secret"
        samples = []
        with _Stub(_WB):
            samples += worldbank.fetch_tenders()
        with _Stub(_TED):
            samples += ted.fetch_tenders()
        with _Stub(_SAM):
            samples += samgov.fetch_tenders()
        with _Stub(_ocds()):
            samples += fcdo.fetch_tenders()
    finally:
        config.SAM_API_KEY = original

    check(len(samples) >= 4, "schema: records came back from all four APIs")
    for record in samples:
        for field_name in base.RECORD_FIELDS:
            check(field_name in record,
                  f"schema: '{field_name}' present on every API record")


TESTS = [
    test_worldbank_parses_documented_shape,
    test_worldbank_accepts_alternative_response_keys,
    test_worldbank_empty_response_is_diagnosed_not_silent,
    test_ted_parses_multilingual_fields,
    test_ted_builds_a_url_when_links_are_missing,
    test_ted_empty_response_is_diagnosed,
    test_samgov_requires_a_key_and_says_so,
    test_samgov_parses_and_filters_to_jordan,
    test_samgov_empty_window_is_normal_not_an_error,
    test_fcdo_parses_ocds_and_excludes_jordanstown,
    test_fcdo_notice_type_survives_a_missing_tag,
    test_fcdo_pagination_terminates,
    test_fcdo_rejects_a_non_dict_response,
    test_every_api_module_returns_the_standard_record,
]
