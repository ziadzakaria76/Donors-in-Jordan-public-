"""--capture must work for every HTML portal, including ones with custom fetch
logic, and must fail honestly when a source is unreachable."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from syria_monitor.fetch import Fetcher, TransportError
from syria_monitor.portals import HTML_PORTALS, REGISTRY

from conftest import fixture


class StubFetcher(Fetcher):
    """Serves a fixture for both GET and POST, so custom fetch logic is covered."""

    def __init__(self, html="<html></html>", status=200):
        super().__init__()
        self._html, self._status = html, status

    def get(self, url, **kwargs):
        from syria_monitor.fetch import Response
        return Response(url=url, status=self._status, text=self._html, headers={})

    def post(self, url, **kwargs):
        return self.get(url, **kwargs)


class DeadFetcher(Fetcher):
    def get(self, url, **kwargs):
        raise TransportError("ConnectionError: name resolution failed")

    def post(self, url, **kwargs):
        return self.get(url, **kwargs)


def build(name, fetcher, profile, gate, cfg=None):
    return REGISTRY[name](cfg or {}, profile, fetcher, gate)


@pytest.mark.parametrize("name", HTML_PORTALS)
def test_capture_works_for_every_html_portal(name, profile, gate):
    """Includes UNGM, whose search is a POST -- capture goes through the same
    fetch_page() the run uses, so custom logic cannot be accidentally excluded."""
    portal = build(name, StubFetcher(fixture("drupal_views.html")), profile, gate,
                   cfg={"country_id": 9999} if name == "ungm" else {})
    captured = portal.capture()
    assert captured, f"{name} captured nothing"
    for label, html, status, result in captured:
        assert status == 200
        assert html
        assert result is not None, f"{name}/{label} produced no extraction report"
        assert result.attempts, "per-layer diagnostics must be reported"


@pytest.mark.parametrize("name", HTML_PORTALS)
def test_capture_fails_honestly_when_unreachable(name, profile, gate):
    portal = build(name, DeadFetcher(), profile, gate,
                   cfg={"country_id": 9999} if name == "ungm" else {})
    captured = portal.capture()
    assert all(html == "" for _, html, _, _ in captured)
    assert getattr(portal, "_capture_error", "").startswith("ConnectionError")


def test_rest_portals_capture_their_payload(profile, gate, monkeypatch):
    from syria_monitor.portals.worldbank import WorldBankPortal

    class JsonFetcher(Fetcher):
        def json(self, url, **kwargs):
            return {"procnotices": [{"id": "OP00460737", "notice_title": "x",
                                     "project_ctry_name": "Syrian Arab Republic"}]}

    captured = WorldBankPortal({}, profile, JsonFetcher(), gate).capture()
    assert captured and "OP00460737" in captured[0][1]


def test_ungm_refuses_to_run_without_its_numeric_country_id(profile, gate):
    """UNGM does not use ISO codes and the id cannot be derived. A wrong id
    returns nothing, silently -- so the portal reports why instead of guessing."""
    portal = build("ungm", StubFetcher(), profile, gate, cfg={"country_id": None})
    reason = portal.unavailable_reason()
    assert reason and "country_id" in reason and "--capture ungm" in reason

    outcome = portal.collect()
    assert outcome.skipped_reason == reason
    assert outcome.tenders == []


def test_ungm_search_body_carries_the_configured_country_id(profile, gate):
    portal = build("ungm", StubFetcher(), profile, gate, cfg={"country_id": 2401})
    body = portal.search_body()
    assert body["Countries"] == [2401]
    assert body["IsActive"] is True


def test_ungm_search_body_matches_the_request_the_ui_actually_sent(profile, gate):
    """Pin the body to the recorded request, field for field.

    Recorded 2026-08-30 from the live listing (Actions run 33282804658). The
    point is not that these values are self-evidently right -- it is that they
    were observed rather than reasoned about, and the previous version was
    reasoned about and wrong in six places.

    A wrong body here does not raise. It returns a short response that reads
    like "no tenders for this country", so nothing downstream will notice the
    drift. This test is the thing that notices.
    """
    from datetime import date

    portal = build("ungm", StubFetcher(), profile, gate,
                   cfg={"country_id": 2490, "page_size": 15})
    body = portal.search_body(page=1)
    today = date.today().strftime("%d-%b-%Y")

    assert body == {
        "PageIndex": 1,
        "PageSize": 15,
        "Title": "",
        "Description": "",
        "Reference": "",
        "PublishedFrom": "",
        "PublishedTo": today,
        "DeadlineFrom": today,
        "DeadlineTo": "",
        "Countries": [2490],
        "Agencies": [],
        "UNSPSCs": [],
        "NoticeTypes": [],
        "SortField": "Deadline",
        "SortAscending": True,
        "isPicker": False,
        "IsSustainable": False,
        "IsActive": True,
        "NoticeDisplayType": None,
        "NoticeSearchTotalLabelId": "noticeSearchTotal",
        "TypeOfCompetitions": [],
    }

    # Called out separately because each is a specific way the old body was
    # wrong, and an equality assertion alone would not say which mattered.
    assert body["SortField"] == "Deadline", "not DeadlineUTC -- see search_body"
    assert "isPicker" in body, "UNGM's own lower-cased spelling, not IsPicker"
    assert body["PublishedTo"] != "", "the UI bounds the upper end"


def test_ungm_deadline_uses_the_countdown_guard(profile, gate):
    """The portal's own row text carries a countdown between the deadline and
    the publication date."""
    from datetime import date
    from syria_monitor.extraction import Row

    portal = build("ungm", StubFetcher(), profile, gate, cfg={"country_id": 2401})
    row = Row(title="Rehabilitation works, Aleppo",
              text="Deadline: 30-Sep-2026 Expires in 38 days Published: 20-Jul-2026")
    record = portal.row_to_record(row, "https://www.ungm.org/Public/Notice/Search")
    assert record["closing_date"] == date(2026, 9, 30).isoformat()


def test_ungm_multiple_destinations_is_not_read_as_another_country(profile, gate):
    """The live run of 2026-08-30 kept 7 of 15 UNGM rows. The 8 it dropped were
    the ones labelled "Multiple destinations" -- a label, not a country, and the
    reason their row text never says Syria.

    They are kept on the strength of the request that produced them: the search
    was filtered to Countries=[country_id], and a column that cannot express a
    country is not the source contradicting that.
    """
    from syria_monitor.extraction import Row

    portal = build("ungm", StubFetcher(), profile, gate, cfg={"country_id": 2490})
    row = Row(title="Provision of equipment for Jobar TVET Centre",
              text="Deadline: 30-Sep-2026 UNDP UNDP-SYR-00659 Multiple destinations")
    record = portal.row_to_record(row, "https://www.ungm.org/Public/Notice/Search")

    assert record.get("country") == "Syria", (
        "a multi-destination row carries the country the search asked for")
    keep, _link, _delivery = gate.check(record)
    assert keep, "and the gate therefore keeps it"


def test_ungm_a_row_naming_another_country_is_still_not_claimed(profile, gate):
    """The other half of the tri-state, and the half that keeps it honest.

    Where the column CAN express a country and names one that is not ours, it is
    the source disagreeing with our request and it is believed. Only the blank
    answer stops being read as a "no".
    """
    from syria_monitor.extraction import Row

    portal = build("ungm", StubFetcher(), profile, gate, cfg={"country_id": 2490})
    row = Row(title="Supply of office furniture",
              text="Deadline: 30-Sep-2026 UNDP UNDP-LBN-00123 Lebanon")
    record = portal.row_to_record(row, "https://www.ungm.org/Public/Notice/Search")
    assert not record.get("country"), "no country is claimed for it"


def test_sam_gov_is_skipped_without_a_key_rather_than_failing(profile, gate):
    outcome = REGISTRY["samgov"]({}, profile, StubFetcher(), gate).collect()
    assert outcome.skipped_reason and "SAM_API_KEY" in outcome.skipped_reason
    assert outcome.available is True          # skipped, not broken


def test_sam_gov_sends_a_legal_date_range(profile, gate, monkeypatch):
    """postedFrom/postedTo are mandatory and the API rejects ranges over a year,
    so the window is an API constraint rather than the lookback policy."""
    from datetime import datetime
    monkeypatch.setenv("SAM_API_KEY", "test-key")
    params = REGISTRY["samgov"]({}, profile, StubFetcher(), gate)._params()
    start = datetime.strptime(params["postedFrom"], "%m/%d/%Y")
    end = datetime.strptime(params["postedTo"], "%m/%d/%Y")
    assert 0 < (end - start).days <= 365
    assert params["ncode"] == "SY"


def test_ted_page_limit_is_never_over_100(profile, gate):
    """250 is a silent HTTP 400 on every run."""
    body = REGISTRY["ted"]({}, profile, StubFetcher(), gate)._body()
    assert body["limit"] <= 100
    assert "SYR" in body["query"]


def test_ted_reads_place_of_performance_not_buyer_country(profile, gate):
    portal = REGISTRY["ted"]({}, profile, StubFetcher(), gate)
    record = portal._to_record({
        "publication-number": "123456-2026",
        "notice-title": {"eng": ["Syria - Rehabilitation of water networks - Aleppo"]},
        "place-of-performance-country-lot": {"eng": ["SYR"]},
        "buyer-country": {"eng": ["DEU"]},
    })
    assert record["place_of_performance_country"] == "SYR"
    assert record["buyer_country"] == "DEU"


def test_ted_title_country_rule_is_strict(profile, gate):
    from syria_monitor.portals.ted import TedPortal
    assert TedPortal.country_from_title("Syria - Water works - Aleppo") == "Syria"
    assert TedPortal.country_from_title("Syrian Arab Republic - Health - Homs") \
        == "Syrian Arab Republic"
    # Not a country name: too long, or carries digits.
    assert TedPortal.country_from_title("Supply of laboratory equipment, Package 3 - Lot 2") is None
    assert TedPortal.country_from_title("2026 framework agreement - services") is None


def test_uk_fts_pagination_cannot_loop_forever(profile, gate):
    """The next-link chain can loop; a seen-set is what terminates the run."""
    from syria_monitor.portals.uk_fts import UkFindATenderPortal

    class LoopingFetcher(Fetcher):
        calls = 0

        def json(self, url, **kwargs):
            LoopingFetcher.calls += 1
            return {"releases": [{"ocid": f"ocds-{LoopingFetcher.calls}",
                                  "tender": {"title": "Works in Aleppo"}}],
                    "links": {"next": "https://find-tender.example/page/1"}}

    records = UkFindATenderPortal({}, profile, LoopingFetcher(), gate).fetch_tenders()
    assert LoopingFetcher.calls <= 3
    assert records


def test_capture_ungm_works_without_the_country_id_it_exists_to_find(profile, gate):
    """The documented way to obtain the id is `--capture ungm`. If capture
    refused to run without the id, that instruction would be impossible to
    follow."""
    portal = build("ungm", StubFetcher(fixture("drupal_views.html")), profile, gate,
                   cfg={"country_id": None})
    labels = [label for label, _ in portal.pages()]
    assert labels == ["dropdown"], "the dropdown page is where the id is read from"

    captured = portal.capture()
    assert captured, "capture must still fetch what it can without the id"
    assert captured[0][0] == "dropdown"


def test_capture_reads_the_country_id_out_of_the_dropdown(profile, gate, capsys):
    """The whole point: turn a live page into the number for config.yml."""
    from syria_monitor.cli import capture
    from syria_monitor.config import Config

    dropdown = ('<html><body><select id="selNoticeCountry">'
                '<option value="2395">Jordan</option>'
                '<option value="2401">Syrian Arab Republic</option>'
                '<option value="2500">Yemen</option>'
                '</select></body></html>')

    class Cfg(Config):
        pass

    cfg = Cfg({"profile": "syria", "portals": {"ungm": {"enabled": True, "country_id": None}}},
              profile)

    import syria_monitor.cli as cli_mod
    original = cli_mod._build

    def stub_build(_cfg, name):
        return build(name, StubFetcher(dropdown), profile, gate, cfg={"country_id": None})

    cli_mod._build = stub_build
    try:
        capture(cfg, "ungm")
    finally:
        cli_mod._build = original

    printed = capsys.readouterr().out
    assert "set portals.ungm.country_id: 2401" in printed
    assert "Syrian Arab Republic" in printed
    assert "2500" not in printed, "only the matching country should be suggested"


SEARCH_URL = "https://www.ungm.org/Public/Notice/Search"


def _ungm_page(n_rows, start=0):
    """Markup shaped like UNGM's search fragment."""
    return "".join(
        '<div class="dataRow notice-table tableRow">'
        '<a class="save-notice-button" href="#">Unsave this procurement opportunity.</a>'
        f'<a href="/Public/Notice/{start + i}">Rehabilitation works, lot {start + i}</a>'
        '<span>Deadline: 30-Sep-2026</span><span>Syrian Arab Republic</span>'
        '</div>'
        for i in range(n_rows)
    )


class PagingFetcher(StubFetcher):
    """Serves a fixed number of notices, PageSize at a time."""

    def __init__(self, total, page_size=15):
        super().__init__()
        self.total, self.page_size, self.requested = total, page_size, []

    def post(self, url, json=None, headers=None, **kw):
        index = json["PageIndex"]
        self.requested.append(index)
        start = index * self.page_size
        count = max(0, min(self.page_size, self.total - start))
        return SimpleNamespace(text=_ungm_page(count, start), status=200, ok=True)


def test_ungm_reads_every_page_not_just_the_first(profile, gate):
    """The capture of 2026-08-30 returned exactly 15 rows against a PageSize of
    15 -- the standard signal that another page exists -- and nothing followed
    it. Everything past the first fifteen open notices was invisible, and a
    short read looked identical to a quiet week.
    """
    fetcher = PagingFetcher(total=38)
    portal = build("ungm", fetcher, profile, gate,
                   cfg={"country_id": 2490, "page_size": 15})

    html, status = portal.fetch_page("search", SEARCH_URL)
    assert status == 200
    assert fetcher.requested == [0, 1, 2], (
        f"three pages for 38 notices, asked for {fetcher.requested}")
    assert len(portal.extract_page(html, SEARCH_URL).rows) == 38, "all 38, not 15"


def test_ungm_stops_on_the_page_size_the_server_actually_returns(profile, gate):
    """The stride is measured from page one, never taken from the request.

    Asking for 15 and being served 10 would make every page look short, and
    "short page" is this loop's end-of-listing signal -- so an unhonoured
    PageSize would stop the read after one page and call it complete.
    """
    fetcher = PagingFetcher(total=25, page_size=10)      # server caps at 10
    portal = build("ungm", fetcher, profile, gate,
                   cfg={"country_id": 2490, "page_size": 15})   # we asked for 15

    html, _status = portal.fetch_page("search", SEARCH_URL)
    assert fetcher.requested == [0, 1, 2], (
        f"kept paging on the served size, asked for {fetcher.requested}")
    assert len(portal.extract_page(html, SEARCH_URL).rows) == 25


def test_ungm_hands_back_a_failing_response_whole(profile, gate):
    """A bad status must reach the diagnostics with its body intact."""
    class Failing(StubFetcher):
        def post(self, url, json=None, headers=None, **kw):
            return SimpleNamespace(text="upstream is down", status=503, ok=False)

    portal = build("ungm", Failing(), profile, gate, cfg={"country_id": 2490})
    html, status = portal.fetch_page("search", SEARCH_URL)
    assert status == 503 and html == "upstream is down"


def test_ungm_stops_when_the_endpoint_ignores_the_page_index(profile, gate):
    """An endpoint serving page one forever satisfies "the page was full" every
    time, so only the cap would stop it -- after concatenating the same listing
    forty times and turning one notice into forty rows.

    Found by this suite: a stub that ignores PageIndex made the fixtures 8x
    slower, which is the same bug wearing a stopwatch.
    """
    class Stuck(StubFetcher):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def post(self, url, json=None, headers=None, **kw):
            self.calls += 1
            return SimpleNamespace(text=_ungm_page(15), status=200, ok=True)

    fetcher = Stuck()
    portal = build("ungm", fetcher, profile, gate,
                   cfg={"country_id": 2490, "page_size": 15})
    html, _status = portal.fetch_page("search", SEARCH_URL)

    assert fetcher.calls == 2, f"one page, then one repeat, then stop: {fetcher.calls}"
    assert len(portal.extract_page(html, SEARCH_URL).rows) == 15, "counted once"


def _live_ungm_row(i, country):
    """The live row anatomy, per the capture of 2026-08-30 (run 33287077057).

    Two save controls wired href="#", the title in a SPAN rather than an
    anchor, and a deadline cell carrying its own class -- the class that beat
    the notice row once there were 87 of them.
    """
    return (
        '<div class="dataRow notice-table tableRow">'
        '<a class="save-notice-button" href="#">Unsave this procurement opportunity. '
        'Subscribe to UNGM Pro to be able to save.</a>'
        '<a class="save-notice-button" href="#">Save</a>'
        f'<div class="resultTitle tableCell"><span class="ungm-title ungm-title--small">'
        f'Provision of equipment for lot {i}</span></div>'
        f'<div class="deadline resultInfo1 tableCell">3{i % 10}-Aug-2026 08:00 (GMT -4.00) 0.41366</div>'
        '<div class="resultInfo1 tableCell">12-Aug-2026</div>'
        '<div class="resultInfo1 tableCell">UNDP</div>'
        f'<div class="resultInfo1 tableCell">UNDP-SYR-006{i:02d}</div>'
        f'<div class="resultInfo1 tableCell">{country}</div>'
        '</div>')


def test_ungm_reads_the_notice_row_not_a_column_of_it(profile, gate):
    """87 deadline cells are 87 well-formed rows, and they are not the notices.

    Live, div.deadline.resultInfo1.tableCell scored 0.83 and beat the real
    div.dataRow.notice-table.tableRow at 0.70, so the run reported
    "0 kept of 87 fetched" -- extraction succeeding on the wrong 87. Quality is
    a heuristic over rows already built; it cannot tell a notice from a column
    of one. The row selector can.
    """
    rows = "".join(_live_ungm_row(i, "Syrian Arab Republic" if i % 2 else
                                  "Multiple destinations") for i in range(1, 88))

    class F(StubFetcher):
        def __init__(s): s.sent = 0
        def post(s, url, json=None, headers=None, **k):
            s.sent += 1
            body = rows if json["PageIndex"] == 0 else ""
            return SimpleNamespace(text=body, status=200, ok=True)
        def get(s, url, **k):
            return SimpleNamespace(text="", status=200, ok=True)

    portal = build("ungm", F(), profile, gate, cfg={"country_id": 2490, "page_size": 15})
    outcome = portal.collect()

    assert outcome.layer == "selectors", (
        f"the pinned row selector must decide this page, not {outcome.layer}")
    assert outcome.stats.seen == 87, f"87 notices, got {outcome.stats.seen}"
    assert len(outcome.tenders) == 87, (
        f"every row carries a country or the multi-destination label; "
        f"kept {len(outcome.tenders)}")
    titles = [t.title for t in outcome.tenders]
    assert all(t.startswith("Provision of equipment") for t in titles), \
        f"titles come from span.ungm-title: {titles[:2]}"
    assert not any("Unsave" in t for t in titles), "never the save button's label"
    assert not any((t.url or "").endswith("#") for t in outcome.tenders), \
        "href='#' is not a link"


def test_undp_rows_are_the_anchors_that_carry_the_notice(profile, gate):
    """572 notices in the markup, six read.

    Every UNDP row carries its country and region in its own class list, so
    grouping by class signature shatters one listing into dozens of per-country
    fragments -- the largest 49, none reaching the 0.45 threshold -- and a
    six-row structural group wins instead. Naming the row answers it.

    The row is ALSO the link: the cells sit inside <a class="vacanciesTableLink">,
    so searching within the row finds no anchor and every notice would come back
    with no URL.
    """
    from syria_monitor.extraction import extract

    rows = "".join(
        f'<a class="country_{i % 8} region_RAS vacanciesTableLink vacanciesTable__row" '
        f'href="/view_notice.cfm?notice_id={1000 + i}">'
        f'<div class="vacanciesTable__cell">Rehabilitation of clinics, lot {i}</div>'
        f'<div class="vacanciesTable__cell">Deadline: 30-Sep-2026</div>'
        f'<div class="vacanciesTable__cell">Syrian Arab Republic</div></a>'
        for i in range(120))
    html = f"<html><body><div>{rows}</div></body></html>"

    loose = extract(html, base_url="https://procurement-notices.undp.org")
    assert len(loose.rows) < 120, (
        "precondition: without the selector the class groups fragment "
        f"(got {len(loose.rows)} via {loose.layer})")

    result = extract(html, base_url="https://procurement-notices.undp.org",
                     selectors={"row": "a.vacanciesTableLink"})
    assert result.layer == "selectors"
    assert len(result.rows) == 120, f"every notice, got {len(result.rows)}"
    assert all(r.url and "notice_id=" in r.url for r in result.rows), \
        "the row is the anchor; its own href is the notice URL"
