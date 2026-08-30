"""--capture must work for every HTML portal, including ones with custom fetch
logic, and must fail honestly when a source is unreachable."""

from __future__ import annotations

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
