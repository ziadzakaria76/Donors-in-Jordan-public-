"""Oracle Recruiting Cloud adapter.

The payloads below are built from Oracle's documented response shape, NOT
recorded from a live tenant — the environment this was written in could not
reach the host. These tests therefore prove the parser handles that shape
correctly; they do not prove the shape is what ROSHN actually returns. That
check happens on the first live run.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.adapters.base import AccessMode
from app.adapters.http import FetchFailed
from app.adapters.oracle_orc import (
    OracleRecruitingAdapter, OracleTenant, PAGE_SIZE, job_url,
    parse_date, parse_requisitions, total_count,
)

TENANT = OracleTenant(
    source_id="test-oracle",
    display_name="Test Employer careers",
    employer="Test Employer",
    base_url="https://fa-test.fa.ocs.oraclecloud.com",
    site_number="CX_1",
)


def requisition(**kw):
    base = {
        "Id": "300001",
        "Title": "Delivery Director",
        "PostedDate": "2026-08-01",
        "PrimaryLocation": "Riyadh, Saudi Arabia",
        "ShortDescriptionStr": "District cooling and MEP delivery.",
    }
    base.update(kw)
    return base


def page(reqs, total=None):
    item = {"requisitionList": reqs}
    if total is not None:
        item["TotalJobsCount"] = total
    return {"items": [item]}


class FakeClient:
    """Returns queued pages and records the parameters it was called with."""

    def __init__(self, pages):
        self._pages = list(pages)
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        if not self._pages:
            return page([])
        return self._pages.pop(0)


# -- parsing -----------------------------------------------------------------

def test_a_requisition_becomes_a_posting_with_a_working_url():
    postings = parse_requisitions(TENANT, page([requisition()]))
    assert len(postings) == 1

    posting = postings[0]
    assert posting.source_job_id == "300001"
    assert posting.title == "Delivery Director"
    assert posting.employer == "Test Employer"
    assert posting.location == "Riyadh, Saudi Arabia"
    assert posting.posted_date == date(2026, 8, 1)
    assert posting.url == (
        "https://fa-test.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/"
        "en/sites/CX_1/job/300001"
    )


def test_alternative_field_spellings_are_accepted():
    """Oracle tenants differ on field names between versions."""
    postings = parse_requisitions(TENANT, page([{
        "RequisitionId": "42",
        "RequisitionTitle": "Programme Director",
        "Location": "Jeddah",
        "ExternalDescriptionStr": "Stadium delivery.",
        "PostingStartDate": "2026-07-15T09:30:00Z",
    }]))
    assert postings[0].source_job_id == "42"
    assert postings[0].title == "Programme Director"
    assert postings[0].location == "Jeddah"
    assert postings[0].posted_date == date(2026, 7, 15)


def test_secondary_locations_are_merged_without_duplicates():
    postings = parse_requisitions(TENANT, page([requisition(
        PrimaryLocation="Riyadh",
        secondaryLocations=[{"Name": "Jeddah"}, {"Name": "Riyadh"}, {}],
    )]))
    assert postings[0].location == "Riyadh; Jeddah"


def test_a_requisition_without_an_id_is_dropped_not_invented():
    postings = parse_requisitions(TENANT, page([
        requisition(),
        {"Title": "Ghost Role", "PrimaryLocation": "Riyadh"},
    ]))
    assert len(postings) == 1
    assert postings[0].source_job_id == "300001"


def test_an_empty_response_yields_nothing_rather_than_failing():
    assert parse_requisitions(TENANT, {"items": []}) == []
    assert parse_requisitions(TENANT, {}) == []


@pytest.mark.parametrize("raw, expected", [
    ("2026-08-01", date(2026, 8, 1)),
    ("2026-08-01T00:00:00", date(2026, 8, 1)),
    ("2026-08-01T12:30:00Z", date(2026, 8, 1)),
    ("2026-08-01T12:30:00+03:00", date(2026, 8, 1)),
    ("", None),
    (None, None),
    ("not a date", None),
])
def test_dates_parse_or_stay_unset(raw, expected):
    assert parse_date(raw) == expected


def test_total_count_is_read_when_present():
    assert total_count(page([requisition()], total=17)) == 17
    assert total_count(page([requisition()])) is None


# -- paging ------------------------------------------------------------------

def test_paging_walks_until_a_short_page():
    full = [requisition(Id=str(i)) for i in range(PAGE_SIZE)]
    tail = [requisition(Id="last")]
    client = FakeClient([page(full), page(tail)])

    postings = OracleRecruitingAdapter(TENANT, client).fetch()

    assert len(postings) == PAGE_SIZE + 1
    assert len(client.calls) == 2
    assert "offset=0," in client.calls[0][1]["finder"]
    assert f"offset={PAGE_SIZE}," in client.calls[1][1]["finder"]


def test_paging_stops_when_the_reported_total_is_reached():
    client = FakeClient([
        page([requisition(Id=str(i)) for i in range(PAGE_SIZE)], total=PAGE_SIZE),
    ])
    postings = OracleRecruitingAdapter(TENANT, client).fetch()
    assert len(postings) == PAGE_SIZE
    assert len(client.calls) == 1


def test_a_tenant_that_ignores_offset_does_not_loop_forever():
    """Some tenants serve page one regardless of offset."""
    stuck = page([requisition(Id="same")] * 1)
    client = FakeClient([stuck] * 30)

    postings = OracleRecruitingAdapter(TENANT, client).fetch()

    assert len(postings) == 1
    assert len(client.calls) <= 2


def test_the_request_targets_the_documented_resource():
    client = FakeClient([page([requisition()])])
    OracleRecruitingAdapter(TENANT, client).fetch()

    url, params = client.calls[0]
    assert url.endswith("/hcmRestApi/resources/latest/recruitingCEJobRequisitions")
    assert params["onlyData"] == "true"
    assert "siteNumber=CX_1" in params["finder"]
    assert "sortBy=POSTING_DATES_DESC" in params["finder"]


# -- failure behaviour -------------------------------------------------------

def test_a_transport_failure_propagates_so_the_runner_records_it():
    class Broken:
        def get_json(self, url, params=None):
            raise FetchFailed("HTML instead of JSON")

    with pytest.raises(FetchFailed):
        OracleRecruitingAdapter(TENANT, Broken()).fetch()


def test_the_adapter_declares_itself_unverified_until_it_has_run_live():
    adapter = OracleRecruitingAdapter(TENANT, FakeClient([]))
    assert adapter.access_mode is AccessMode.FETCH
    assert "NOT YET VERIFIED" in adapter.repair_note
    assert "network tab" in adapter.repair_note, "the repair note must be actionable"
