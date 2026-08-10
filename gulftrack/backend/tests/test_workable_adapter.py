"""Workable adapter.

The payloads below are trimmed copies of a response observed live from the
Qiddiya board on 10 August 2026 — field names, nesting and value shapes are as
they actually came back, not as documentation describes them. That is the
difference between these tests and the Oracle ones.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.adapters.http import FetchFailed
from app.adapters.workable import (
    QIDDIYA, WorkableAdapter, WorkableBoard, format_location, job_url,
    parse_published, parse_results, strip_html,
)

BOARD = WorkableBoard(
    source_id="test-workable",
    display_name="Test board",
    employer="Test Employer",
    account="test-account-1",
)


def result(**kw):
    # Shape copied from the observed response.
    base = {
        "id": 6020481,
        "shortcode": "26A1882738",
        "title": "Manager - IT Security Delivery",
        "remote": False,
        "location": {
            "country": "Saudi Arabia", "countryCode": "SA",
            "city": "Riyadh", "region": "Riyadh Province",
        },
        "locations": [{"country": "Saudi Arabia", "city": "Riyadh"}],
        "state": "published",
        "isInternal": False,
        "code": None,
        "published": "2026-08-10T00:00:00.000Z",
        "type": "full",
        "language": "en",
        "department": ["Qiddiya Technology"],
        "workplace": "on_site",
    }
    base.update(kw)
    return base


def page(results, next_page=None):
    payload = {"total": len(results), "results": results}
    if next_page:
        payload["nextPage"] = next_page
    return payload


class FakeClient:
    def __init__(self, pages, details=None):
        self._pages = list(pages)
        self._details = details or {}
        self.posts = []
        self.gets = []

    def post_json(self, url, json_body=None):
        self.posts.append((url, json_body))
        return self._pages.pop(0) if self._pages else page([])

    def get_json(self, url, params=None):
        self.gets.append(url)
        shortcode = url.rsplit("/", 1)[-1]
        if shortcode not in self._details:
            raise FetchFailed(f"HTTP 404 from {url}")
        return self._details[shortcode]


# -- parsing -----------------------------------------------------------------

def test_a_result_becomes_a_posting_with_a_working_url():
    postings = parse_results(BOARD, page([result()]))
    assert len(postings) == 1

    posting = postings[0]
    assert posting.source_job_id == "26A1882738"
    assert posting.title == "Manager - IT Security Delivery"
    assert posting.employer == "Test Employer"
    assert posting.location == "Riyadh, Riyadh Province, Saudi Arabia"
    assert posting.posted_date == date(2026, 8, 10)
    assert posting.url == "https://apply.workable.com/test-account-1/j/26A1882738/"


def test_internal_and_unpublished_postings_are_not_matches():
    postings = parse_results(BOARD, page([
        result(shortcode="A", isInternal=True),
        result(shortcode="B", state="draft"),
        result(shortcode="C"),
    ]))
    assert [p.source_job_id for p in postings] == ["C"]


def test_a_result_without_a_shortcode_is_dropped_not_invented():
    postings = parse_results(BOARD, page([
        result(),
        {"title": "Ghost", "location": {"city": "Riyadh"}},
    ]))
    assert len(postings) == 1


def test_a_remote_posting_says_so_in_its_location():
    postings = parse_results(BOARD, page([result(remote=True)]))
    assert postings[0].location.endswith("Remote")


def test_location_survives_missing_pieces():
    assert format_location({"location": {"city": "Jeddah"}}) == "Jeddah"
    assert format_location({"location": {}}) is None
    assert format_location({}) is None


def test_duplicate_location_parts_are_not_repeated():
    entry = {"location": {"city": "Riyadh", "region": "Riyadh", "country": "Saudi Arabia"}}
    assert format_location(entry) == "Riyadh, Saudi Arabia"


@pytest.mark.parametrize("raw, expected", [
    ("2026-08-10T00:00:00.000Z", date(2026, 8, 10)),
    ("2026-08-10", date(2026, 8, 10)),
    (None, None),
    ("nonsense", None),
])
def test_published_dates_parse_or_stay_unset(raw, expected):
    assert parse_published(raw) == expected


def test_the_real_qiddiya_board_is_configured():
    assert QIDDIYA.account == "qiddiya-investment-company-1"
    assert job_url(QIDDIYA, "X").startswith("https://apply.workable.com/")


# -- html --------------------------------------------------------------------

def test_description_html_is_reduced_to_words():
    html = (
        "<div><p>Lead <b>district cooling</b> delivery.</p>"
        "<script>var x=1;</script><ul><li>FIDIC &amp; EOT</li></ul></div>"
    )
    text = strip_html(html)
    assert "district cooling" in text
    assert "FIDIC & EOT" in text
    assert "var x" not in text
    assert "<" not in text


# -- fetching ----------------------------------------------------------------

def test_the_list_is_requested_by_post_because_get_returns_not_found():
    client = FakeClient([page([result()])])
    WorkableAdapter(BOARD, client, fetch_descriptions=False).fetch()

    url, body = client.posts[0]
    assert url == "https://apply.workable.com/api/v3/accounts/test-account-1/jobs"
    assert "token" not in body, "the first page carries no cursor"
    # The endpoint 400s on an unexpected key, so the body must stay exactly the
    # shape that was verified against the live board.
    assert set(body) == {"query", "location", "department", "worktype", "remote"}


def test_paging_follows_the_next_page_token():
    client = FakeClient([
        page([result(shortcode="A")], next_page="tok-2"),
        page([result(shortcode="B")]),
    ])
    postings = WorkableAdapter(BOARD, client, fetch_descriptions=False).fetch()

    assert [p.source_job_id for p in postings] == ["A", "B"]
    assert client.posts[1][1]["token"] == "tok-2"


def test_paging_stops_when_a_board_repeats_itself():
    client = FakeClient([page([result(shortcode="A")], next_page="t")] * 30)
    postings = WorkableAdapter(BOARD, client, fetch_descriptions=False).fetch()
    assert len(postings) == 1


def test_descriptions_are_fetched_and_stripped():
    client = FakeClient(
        [page([result(shortcode="A")])],
        details={"A": {
            "description": "<p>Delivery of the <b>district cooling</b> energy centre.</p>",
            "requirements": "<ul><li>FIDIC, EOT and claims</li></ul>",
        }},
    )
    postings = WorkableAdapter(BOARD, client).fetch()

    assert "district cooling" in postings[0].description
    assert "FIDIC" in postings[0].description
    assert "<p>" not in postings[0].description
    # The department summary from the list is kept alongside it.
    assert "Qiddiya Technology" in postings[0].description


def test_a_posting_whose_description_fails_is_kept_not_dropped():
    """A secondary request failing must not hide a real job."""
    client = FakeClient([page([result(shortcode="A"), result(shortcode="B")])],
                        details={"A": {"description": "<p>Stadium delivery.</p>"}})
    postings = WorkableAdapter(BOARD, client).fetch()

    assert len(postings) == 2
    assert "Stadium delivery" in postings[0].description
    assert postings[1].description == "Qiddiya Technology"


def test_the_description_cap_keeps_every_posting():
    client = FakeClient(
        [page([result(shortcode=str(i)) for i in range(5)])],
        details={str(i): {"description": f"<p>Job {i}</p>"} for i in range(5)},
    )
    postings = WorkableAdapter(BOARD, client, max_descriptions=2).fetch()

    assert len(postings) == 5, "capping enrichment must not drop postings"
    assert len(client.gets) == 2


def test_the_adapter_states_that_the_list_needs_post():
    adapter = WorkableAdapter(BOARD, FakeClient([]))
    assert "POST, not GET" in adapter.repair_note
    assert "network tab" in adapter.repair_note
