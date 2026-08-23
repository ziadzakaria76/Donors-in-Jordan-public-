"""Date parsing traps. Each one produces a plausible wrong answer and no error."""

from __future__ import annotations

from datetime import date

import pytest

from syria_monitor.dates import CLOSING_LABELS, find_labelled_date, is_open, parse_date


@pytest.mark.parametrize("month", range(1, 13))
@pytest.mark.parametrize("day", range(1, 13))
def test_iso_timestamps_are_not_read_day_first(month, day):
    """The (?!\\d) guard.

    An ISO timestamp ends the day with "T", which is a word character, so a \\b
    guard fails, the ISO branch is skipped and dateutil with dayfirst=True reads
    2026-06-01 as 6 January. The bug is invisible exactly where both numbers are
    <= 12, which is the whole range tested here.
    """
    value = f"2026-{month:02d}-{day:02d}T09:00:00Z"
    assert parse_date(value) == date(2026, month, day)


def test_iso_date_without_time_still_parses():
    assert parse_date("2026-06-01") == date(2026, 6, 1)


@pytest.mark.parametrize("text,expected", [
    ("31.12.2026", date(2026, 12, 31)),          # German dotted
    ("15. Januar 2027", date(2027, 1, 15)),      # German month name
    ("1. März 2026", date(2026, 3, 1)),
    ("15 octobre 2026", date(2026, 10, 15)),     # French
    ("١٥ تشرين الأول ٢٠٢٦", date(2026, 10, 15)),  # Levantine Arabic + Arabic-Indic digits
    ("١٥ أكتوبر ٢٠٢٦", date(2026, 10, 15)),       # Gulf/Egyptian Arabic month names
    ("٣ كانون الثاني ٢٠٢٧", date(2027, 1, 3)),
])
def test_non_english_dates(text, expected):
    assert parse_date(text) == expected


# The literal UNGM row shape: a countdown sits between the real deadline and the
# publication date, so "find the closing label, take the next date" lands on the
# publication date -- months earlier, therefore dropped as closed, therefore the
# portal's entire open pipeline disappears silently.
UNGM_ROW = ("Reference RFP/2026/1234 | Deadline: 30-Sep-2026 | "
            "Expires in 38 days | Published: 20-Jul-2026")


def test_countdown_between_label_and_date_is_voided():
    assert find_labelled_date(UNGM_ROW, CLOSING_LABELS) == date(2026, 9, 30)


def test_countdown_alone_yields_nothing_rather_than_the_wrong_date():
    row = "Expires in 38 days | Published: 20-Jul-2026"
    assert find_labelled_date(row, ("expires",)) is None


@pytest.mark.parametrize("unit", ["hours", "days", "weeks", "months", "years",
                                  "Tagen", "mois", "أيام"])
def test_countdown_units(unit):
    row = f"Expires in 12 {unit} | Published: 20-Jul-2026"
    assert find_labelled_date(row, ("expires",)) is None


def test_deadline_of_today_is_open():
    today = date(2026, 8, 23)
    assert is_open(today, today) is True
    assert is_open(date(2026, 8, 22), today) is False
    assert is_open(None, today) is True          # unknown deadline: kept and flagged
