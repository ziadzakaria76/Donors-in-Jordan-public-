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
    # The title comes from the NOTICE with the project appended as context --
    # see test_worldbank_titles_are_per_notice_not_per_project for why.
    check("Consulting services for treasury modernisation" in r["title"],
          "worldbank: title is the notice description")
    check("Jordan Public Financial Management Reform" in r["title"],
          "worldbank: with the project name as context")
    check_eq(r["posted_date"], date(2026, 6, 1), "worldbank: posted date")
    check_eq(r["closing_date"], date(2026, 9, 15), "worldbank: closing date")
    check_eq(r["estimated_value_usd"], 1_850_000.0, "worldbank: value in USD")
    check_eq(r["portal"], "worldbank", "worldbank: portal tagged")
    check(r["url"].startswith("https://"), "worldbank: url carried through")
    check_eq(records[1]["estimated_value_usd"], None,
             "worldbank: an unpublished value stays None rather than becoming 0")


def test_worldbank_builds_a_link_when_the_api_sends_no_url_field():
    """Every World Bank row reached the report unlinked, and nothing said so.

    The fixture above carries a "url" key, which is what let four wrong guesses
    in _pick() pass their tests for months: the fixture was written to the
    shape the module hoped for, not the shape the API sends. The live response
    has no URL field at all, so 20 of 27 opportunities in a clean run were
    unclickable. This is the same response WITHOUT that key.
    """
    payload = {"procnotices": [
        {"id": "OP00291234",
         "project_name": "Jordan Public Financial Management Reform",
         "bid_description": "Consulting services for treasury modernisation.",
         "project_id": "P175447"},
    ]}
    with _Stub(payload):
        records = worldbank.fetch_tenders()
    check_eq(len(records), 1, "worldbank: the notice still parses without a url")
    check_eq(records[0]["url"],
             "https://projects.worldbank.org/en/projects-operations/"
             "procurement-detail/OP00291234",
             "worldbank: the link is built from the notice id")


def test_worldbank_prefers_the_apis_own_url_over_a_built_one():
    """If the response ever does carry a link, that is the authoritative one."""
    payload = {"procnotices": [
        {"id": "OP00291234",
         "bid_description": "Consulting services, Amman, Jordan.",
         "notice_url": "https://projects.worldbank.org/somewhere/else"},
    ]}
    with _Stub(payload):
        records = worldbank.fetch_tenders()
    check_eq(records[0]["url"], "https://projects.worldbank.org/somewhere/else",
             "worldbank: a real URL field wins over the constructed one")


def test_worldbank_will_not_invent_a_link_from_a_project_id():
    """A dead link is worse than no link: absent is visibly missing, dead reads as checked.

    Project ids (P175447) and notice ids (OP00291234) sit in the same response
    and both look like identifiers. Rendering a project id into the notice-page
    template produces a URL that resolves to nothing.
    """
    payload = {"procnotices": [
        {"project_id": "P175447",
         "notice_no": "RFP-2026-014",
         "bid_description": "Consulting services, Amman, Jordan."},
    ]}
    with _Stub(payload):
        records = worldbank.fetch_tenders()
    check_eq(len(records), 1, "worldbank: the notice is still reported")
    check_eq(records[0]["url"], None,
             "worldbank: no link rather than a fabricated one")


def test_field_anatomy_reports_what_a_response_carries():
    """The diagnostic that would have caught the missing URL field in one run."""
    items = [
        {"id": "OP001", "title": "A", "notice_url": "https://example.org/1"},
        {"id": "OP002", "title": "B"},
        {"id": "OP003", "title": "C", "empty": ""},
    ]
    lines = "\n".join(base.field_anatomy(items))
    check("3 notices" in lines, "field_anatomy: counts the notices")
    check("id" in lines and "3/3" in lines,
          "field_anatomy: reports a field present on every notice")
    check("1/3" in lines,
          "field_anatomy: fill rate distinguishes a rare field from a common one")
    check("URL-ish" in lines, "field_anatomy: flags the field a link could come from")
    check("empty" not in lines,
          "field_anatomy: a key whose only value is empty does not count as populated")


def test_every_api_portal_diagnostic_is_reachable_from_the_cli():
    """--capture covered the HTML portals only, which is how this bug survived."""
    from jordan_tender_monitor import portals
    check("worldbank" in portals.api_portals(),
          "capture: the World Bank API can be inspected from the command line")


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


def test_worldbank_filters_to_jordan_even_when_the_api_does_not():
    """The API ignores countryshortname. Pinning the fix so it cannot regress.

    The first live run proved this: the endpoint returned 200 worldwide
    notices -- Pakistan, Laos, Bolivia, the Caribbean -- and because this module
    trusted the parameter and skipped jordan_only(), the report led with a
    Caribbean education project. Never trust a source's own country filter.
    """
    worldwide = {"procnotices": [
        {"id": "1", "project_name": "Jordan Public Financial Management Reform",
         "bid_description": "Consulting services in Amman.",
         "noticedate": "2026-06-01T00:00:00Z"},
        {"id": "2", "project_name": "Sindh Water and Agriculture Transformation",
         "bid_description": "Irrigation works in Pakistan.",
         "noticedate": "2026-06-01T00:00:00Z"},
        {"id": "3", "project_name": "Lao PDR Climate Resilient Road Connectivity",
         "bid_description": "Road works in Laos.",
         "noticedate": "2026-06-01T00:00:00Z"},
        {"id": "4", "project_name": "Windward Islands Sector Transformation",
         "bid_description": "Education in the Caribbean.",
         "noticedate": "2026-06-01T00:00:00Z"},
    ]}
    with _Stub(worldwide):
        records = worldbank.fetch_tenders()

    check_eq(len(records), 1,
             "worldbank: only the Jordan notice survives a worldwide response")
    check("Jordan" in records[0]["title"],
          "worldbank: and it is the right one")
    titles = " ".join(r["title"] for r in records)
    for phantom in ("Sindh", "Lao PDR", "Windward"):
        check(phantom not in titles,
              f"worldbank: '{phantom}' is not reported as a Jordan opportunity")


def test_every_api_module_applies_the_jordan_filter():
    """No module may trust its source's country filter. Enforced structurally."""
    import inspect
    from jordan_tender_monitor.portals import fcdo, samgov, ted, worldbank as wb

    for name, module in (("worldbank", wb), ("ted", ted),
                         ("samgov", samgov), ("fcdo", fcdo)):
        source = inspect.getsource(module)
        check("jordan_only" in source,
              f"schema: {name} filters to Jordan client-side, whatever the API claims")


def test_scan_count_distinguishes_empty_from_filtered_out():
    """'OK: 0' must not be ambiguous.

    Returned nothing, or returned 500 worldwide notices of which none were
    Jordan? Those need entirely different fixes, and the first live run cost
    real time to diagnose because the number shown was post-filter only.
    """
    base.take_scanned()          # clear any residue
    check_eq(base.take_scanned(), None, "scan-count: starts empty")

    records = [base.build_record(portal="worldbank", title=t)
               for t in ("Advisory Services, Jordan", "Road works in Laos",
                         "Education in the Caribbean")]
    kept = base.jordan_only(records)
    check_eq(len(kept), 1, "scan-count: one Jordan record survives")
    check_eq(base.take_scanned(), 3,
             "scan-count: the pre-filter total is recorded")
    check_eq(base.take_scanned(), None,
             "scan-count: reading it clears it, so portals cannot inherit "
             "each other's numbers")


def test_worldbank_titles_are_per_notice_not_per_project():
    """One project raises many notices; they must not all share a title.

    Reading the title from project_name made six different notices appear as
    six identical lines of "Jordan Education Reform Support Program" in the
    first corrected live run.
    """
    payload = {"procnotices": [
        {"id": "1", "project_name": "Jordan Education Reform Support Program",
         "bid_description": "Consultancy for curriculum assessment, Amman",
         "noticedate": "2026-06-01T00:00:00Z"},
        {"id": "2", "project_name": "Jordan Education Reform Support Program",
         "bid_description": "Supply of school laboratory equipment, Irbid",
         "noticedate": "2026-06-02T00:00:00Z"},
        {"id": "3", "project_name": "Jordan Education Reform Support Program",
         "notice_title": "Teacher training programme evaluation, Jordan",
         "noticedate": "2026-06-03T00:00:00Z"},
    ]}
    with _Stub(payload):
        records = worldbank.fetch_tenders()

    check_eq(len(records), 3, "worldbank: all three notices are kept")
    titles = [r["title"] for r in records]
    check(len(set(titles)) == 3,
          "worldbank: three notices produce three DISTINCT titles",
          f"got {titles}")
    check(any("curriculum" in t for t in titles),
          "worldbank: the notice description drives the title")
    check(all("Jordan Education Reform" in t for t in titles),
          "worldbank: the project name is retained as context")
    check(len({r["id"] for r in records}) == 3,
          "worldbank: and each keeps a distinct identity")


def test_worldbank_country_field_beats_a_full_text_match():
    """VERIFIED LIVE: the text filter was a no-op, and kept 500 of 500.

    qterm=Jordan is a FULL-TEXT search, so every notice the API returns has the
    word "Jordan" somewhere in its indexed text -- and this module stores that
    same searched body as the record description. The client-side text filter
    therefore could not reject anything the API returned, and the report
    carried water-supply consultancies in Blantyre, Malawi as Jordan
    opportunities. Defence in depth is not depth when both layers read the
    same field.
    """
    payload = {"procnotices": [
        # Malawi. Mentions Jordan only as desirable prior experience -- a
        # genuine full-text hit AND a genuine non-Jordan tender.
        {"id": "1", "project_ctry_name": "Malawi",
         "bid_description": "Consultancy for supervision of Blantyre water supply",
         "notice_text": "Prior experience in Jordan and Egypt is an advantage.",
         "noticedate": "2026-06-01T00:00:00Z"},
        # Jordan by country field, and its text names neither Jordan nor Amman.
        # The old text filter would have DROPPED this real tender.
        {"id": "2", "project_ctry_name": "Jordan",
         "bid_description": "Supply of laboratory equipment, Package 3",
         "notice_text": "Sealed bids are invited from eligible bidders.",
         "noticedate": "2026-06-02T00:00:00Z"},
        # No country field at all: the text check is the only signal, and it
        # is still applied.
        {"id": "3", "bid_description": "Advisory Services, Amman, Jordan",
         "noticedate": "2026-06-03T00:00:00Z"},
        {"id": "4", "bid_description": "Road works, Lilongwe",
         "noticedate": "2026-06-04T00:00:00Z"},
    ]}
    base.take_scanned()
    with _Stub(payload):
        records = worldbank.fetch_tenders()
    scanned = base.take_scanned()

    titles = [r["title"] for r in records]
    check(len(records) == 2, "worldbank: two of four notices survive",
          f"got {titles}")
    check(not any("Blantyre" in t for t in titles),
          "worldbank: a Malawi notice is rejected despite matching the full-text search")
    check(any("laboratory equipment" in t for t in titles),
          "worldbank: a Jordan notice is KEPT even though its text never says Jordan",
          f"got {titles}")
    check(any("Amman" in t for t in titles),
          "worldbank: a notice with no country field still passes on its text")
    check(not any("Lilongwe" in t for t in titles),
          "worldbank: and is still rejected when the text does not match")
    check_eq(scanned, 4,
             "worldbank: the pre-filter total counts every notice read, not "
             "just the slice the text filter saw")


def _wb_page(count: int, offset: int = 0, total: int | None = None) -> dict:
    """A World Bank page of `count` Jordan-coded notices."""
    payload = {"procnotices": [
        {"id": f"OP{offset + i:06d}",
         "project_ctry_name": "Jordan",
         "bid_description": f"Consultancy package {offset + i}",
         "noticedate": "2026-06-01T00:00:00Z"}
        for i in range(count)
    ]}
    if total is not None:
        payload["total"] = str(total)
    return payload


def test_worldbank_pages_instead_of_reading_the_first_500():
    """'500 read' was the row cap, not the result size.

    Asking for 500 and getting exactly 500 is what a truncated read looks like
    from outside: the number equals the request, so a complete result and a
    capped one are indistinguishable. Jordan notices past the five-hundredth
    were invisible and nothing said so.
    """
    offsets = []

    def paged(url, **kwargs):
        offset = kwargs.get("params", {}).get("os", 0)
        offsets.append(offset)
        # Two full pages, then a short one: 500, 500, 7.
        if offset >= 1000:
            return _wb_page(7, offset)
        return _wb_page(worldbank.PAGE_SIZE, offset)

    with _Stub(paged):
        records = worldbank.fetch_tenders()

    check_eq(offsets, [0, 500, 1000],
             "worldbank: it pages by offset until a page comes back short")
    check_eq(len(records), 1007,
             "worldbank: and keeps every notice from every page")
    check(len({r["id"] for r in records}) == 1007,
          "worldbank: the pages are distinct, not the same page three times")


def test_worldbank_stops_at_the_total_the_api_reports():
    """A full last page must not cost an extra request when the total is known."""
    calls = []

    def paged(url, **kwargs):
        offset = kwargs.get("params", {}).get("os", 0)
        calls.append(offset)
        return _wb_page(worldbank.PAGE_SIZE, offset, total=1000)

    with _Stub(paged):
        records = worldbank.fetch_tenders()

    check_eq(calls, [0, 500],
             "worldbank: two pages reach the reported total of 1000, and it stops")
    check_eq(len(records), 1000, "worldbank: with every notice kept")


def test_worldbank_says_so_when_the_page_cap_truncates():
    """The whole point of the fix: a cap that is reached must not be silent."""
    import logging

    records_logged = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records_logged.append(record)

    handler = _Capture()
    log = logging.getLogger("jordan_tender_monitor.portals.worldbank")
    logging.disable(logging.NOTSET)      # the suite disables logging globally
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        def endless(url, **kwargs):
            offset = kwargs.get("params", {}).get("os", 0)
            # Always a full page, and the API says there are far more.
            return _wb_page(worldbank.PAGE_SIZE, offset, total=99_000)

        with _Stub(endless):
            records = worldbank.fetch_tenders()

        check_eq(len(records), worldbank.MAX_PAGES * worldbank.PAGE_SIZE,
                 "worldbank: the cap bounds the read")
        warnings = [r for r in records_logged if r.levelno >= logging.WARNING]
        check(warnings, "worldbank: reaching the cap is reported, not swallowed")
        if warnings:
            message = warnings[0].getMessage()
            check("99000" in message.replace(",", ""),
                  "worldbank: the message names how many notices exist",
                  f"got {message!r}")
            check("NOT read" in message,
                  "worldbank: and says plainly that the rest were not read",
                  f"got {message!r}")
    finally:
        log.removeHandler(handler)
        logging.disable(logging.CRITICAL)


def test_worldbank_country_field_accepts_several_spellings():
    """The field name could not be confirmed, so several are read."""
    for field_name in ("project_ctry_name", "countryshortname", "country_name",
                       "countryname", "country"):
        payload = {"procnotices": [
            {"id": "x", field_name: "Malawi",
             "bid_description": "Works in Blantyre",
             "notice_text": "Experience in Jordan preferred.",
             "noticedate": "2026-06-01T00:00:00Z"},
            {"id": "y", field_name: "Jordan",
             "bid_description": "Institutional support, Package 1",
             "noticedate": "2026-06-01T00:00:00Z"},
        ]}
        with _Stub(payload):
            records = worldbank.fetch_tenders()
        check_eq(len(records), 1, f"worldbank: '{field_name}' is read as the country")
        check("Institutional support" in records[0]["title"],
              f"worldbank: and '{field_name}' selects the right notice")


def test_a_4xx_body_is_reported_not_discarded():
    """TED answered "HTTP 400" for days while explaining itself in the body.

    A JSON API's 4xx body names the parameter it disliked. Discarding it turned
    a one-line fix into guesswork about the query grammar.
    """
    import requests

    class _Response:
        status_code = 400
        text = ('{\n  "message": "Invalid value for parameter limit: '
                'maximum is 100"\n}')

    detail = base._error_detail(_Response())
    check("maximum is 100" in detail,
          "4xx body: the endpoint's own explanation is carried through")
    check("\n" not in detail,
          "4xx body: newlines are stripped -- this goes in a status line")

    long_html = type("R", (), {"status_code": 400, "text": "<html>" + "x" * 5000})()
    check(len(base._error_detail(long_html)) < 400,
          "4xx body: an HTML error page cannot flood the report")

    check_eq(base._error_detail(None), "",
             "4xx body: no response is not an error in itself")

    class _Exploding:
        status_code = 400

        @property
        def text(self):
            raise RuntimeError("body could not be decoded")

    check_eq(base._error_detail(_Exploding()), "",
             "4xx body: diagnosing a failure must not itself fail")

    # And it reaches the PortalError a portal actually raises.
    original = base._request

    def fake_request(method, url, **kwargs):
        response = requests.Response()
        response.status_code = 400
        response._content = b'{"message":"unknown field: place-of-performance"}'
        response.raise_for_status()

    try:
        base._request = fake_request
        try:
            base.post_json("https://api.example/search", {})
            check(False, "4xx body: a 400 must raise")
        except PortalError as exc:
            check("unknown field" in exc.reason,
                  "4xx body: the reason a portal reports names the bad field",
                  f"got {exc.reason!r}")
    finally:
        base._request = original


def test_ted_request_matches_the_documented_contract():
    """Both defects that made every TED run a 400."""
    check(ted.PAGE_LIMIT <= 100,
          "ted: the page limit is within the documented maximum of 100",
          f"got {ted.PAGE_LIMIT}")
    check("JOR" in ted.QUERY,
          "ted: the country is the three-letter ISO code",
          f"got {ted.QUERY!r}")
    check("(JO)" not in ted.QUERY,
          "ted: and not the two-letter code that was rejected")

    sent = {}
    original = base.post_json
    try:
        base.post_json = lambda url, payload, **kw: sent.update(payload) or _TED
        ted.fetch_tenders()
    finally:
        base.post_json = original
    check(sent.get("limit", 999) <= 100,
          "ted: the request actually sent respects the limit",
          f"sent limit={sent.get('limit')}")


def test_ted_country_field_beats_a_full_text_match():
    """FT~"Jordan" is full-text, so text filtering alone cannot reject anything.

    TED is EU-wide. Getting this wrong would put the whole of European
    procurement in the report labelled as Jordan opportunities -- the World
    Bank failure, at a much larger scale.
    """
    payload = {"notices": [
        {"publication-number": "1-2026",
         "notice-title": {"eng": ["Bridge maintenance, Bavaria"]},
         "place-of-performance-country-lot": {"eng": ["DEU"]},
         "description-lot": {"eng": ["Consultants with Jordan experience welcome."]},
         "publication-date": "2026-06-01"},
        {"publication-number": "2-2026",
         "notice-title": {"eng": ["Technical assistance, package 4"]},
         "place-of-performance-country-lot": {"eng": ["JOR"]},
         "description-lot": {"eng": ["Support to public administration reform."]},
         "publication-date": "2026-06-02"},
        {"publication-number": "3-2026",
         "notice-title": {"eng": ["Advisory Services, Amman, Jordan"]},
         "description-lot": {"eng": ["No country coded on this notice."]},
         "publication-date": "2026-06-03"},
    ]}
    with _Stub(payload):
        records = ted.fetch_tenders()

    titles = [r["title"] for r in records]
    check(len(records) == 2, "ted: two of three notices survive", f"got {titles}")
    check(not any("Bavaria" in t for t in titles),
          "ted: a German notice is rejected despite the full-text hit")
    check(any("package 4" in t for t in titles),
          "ted: a JOR-coded notice is kept even though its text never says Jordan",
          f"got {titles}")
    check(any("Amman" in t for t in titles),
          "ted: an uncoded notice still passes on its text")


def test_ted_title_prefix_rejects_another_country():
    """VERIFIED LIVE: an Austrian notice reached the report on a full-text hit.

    TED returned no country field for it, so the text check was the only thing
    left and "Jordan" appeared somewhere in the body. TED does state the
    country in its own title prefix -- "Austria – License management software
    development services – ..." -- so that prefix is used to REJECT.

    It never admits. A prefix reading "Jordan" is good evidence, but admitting
    on it would re-open the same hole from the other side.
    """
    check_eq(ted._country_from_title(
        "Austria – License management software development services – DB"), False,
        "ted title: an Austrian prefix rejects the notice")
    check_eq(ted._country_from_title("Germany – Road works"), False,
             "ted title: so does a German one")
    check_eq(ted._country_from_title("Jordan – Technical assistance"), None,
             "ted title: a Jordan prefix does NOT admit -- it defers")
    check_eq(ted._country_from_title("Technical Assistance for Reform, Jordan"), None,
             "ted title: no prefix means no verdict")
    check_eq(ted._country_from_title("Supply of 12 – 15 laptops"), None,
             "ted title: a dash that is not a country prefix is ignored")
    check_eq(ted._country_from_title(None), None, "ted title: no title, no verdict")

    payload = {"notices": [
        {"publication-number": "9-2026",
         "notice-title": {"eng": ["Austria – License management – Provision of DB "
                                  "hardware"]},
         "description-lot": {"eng": ["Bidders with Jordan experience welcome."]},
         "publication-date": "2026-06-01"},
        {"publication-number": "10-2026",
         "notice-title": {"eng": ["Advisory Services, Amman, Jordan"]},
         "description-lot": {"eng": ["Public administration reform."]},
         "publication-date": "2026-06-02"},
    ]}
    with _Stub(payload):
        records = ted.fetch_tenders()
    titles = [r["title"] for r in records]
    check_eq(len(records), 1, "ted title: the Austrian notice is kept out")
    check("Amman" in titles[0], "ted title: and the Jordan one is kept")


def test_ted_country_codes_are_matched_exactly():
    """"JO" must not match by substring, in either direction."""
    check_eq(ted._country_verdict({"buyer-country": "JOR"}), True,
             "ted: JOR is Jordan")
    check_eq(ted._country_verdict({"buyer-country": "DEU"}), False,
             "ted: DEU is not")
    check_eq(ted._country_verdict({"buyer-country": "COD"}), False,
             "ted: a code merely containing the letters is not Jordan")
    check_eq(ted._country_verdict({"buyer-country": "Jordan"}), True,
             "ted: a country NAME is matched too")
    check_eq(ted._country_verdict({"buyer-country": "Jordanstown"}), False,
             "ted: and Jordanstown is still not Jordan")
    check_eq(ted._country_verdict({}), None,
             "ted: no country field yields no verdict, not a rejection")


TESTS = [
    test_worldbank_parses_documented_shape,
    test_a_4xx_body_is_reported_not_discarded,
    test_ted_request_matches_the_documented_contract,
    test_ted_country_field_beats_a_full_text_match,
    test_ted_title_prefix_rejects_another_country,
    test_ted_country_codes_are_matched_exactly,
    test_worldbank_country_field_beats_a_full_text_match,
    test_worldbank_pages_instead_of_reading_the_first_500,
    test_worldbank_stops_at_the_total_the_api_reports,
    test_worldbank_says_so_when_the_page_cap_truncates,
    test_worldbank_country_field_accepts_several_spellings,
    test_worldbank_filters_to_jordan_even_when_the_api_does_not,
    test_worldbank_titles_are_per_notice_not_per_project,
    test_every_api_module_applies_the_jordan_filter,
    test_scan_count_distinguishes_empty_from_filtered_out,
    test_worldbank_accepts_alternative_response_keys,
    test_worldbank_empty_response_is_diagnosed_not_silent,
    test_worldbank_builds_a_link_when_the_api_sends_no_url_field,
    test_worldbank_prefers_the_apis_own_url_over_a_built_one,
    test_worldbank_will_not_invent_a_link_from_a_project_id,
    test_field_anatomy_reports_what_a_response_carries,
    test_every_api_portal_diagnostic_is_reachable_from_the_cli,
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
