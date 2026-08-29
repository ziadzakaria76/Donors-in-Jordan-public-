"""Extraction cascade: the CMS shapes these portals actually use, plus the
failure modes that need different fixes."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from syria_monitor.extraction import (QUALITY_THRESHOLD, cell_text, diagnose, extract,
                                      feed_layer, structural_layer, table_layer)

from conftest import fixture


@pytest.mark.parametrize("name", [
    "drupal_views.html", "bootstrap_cards.html", "giz_header_table.html",
    "nextjs.html", "jsonld_site_only.html", "arabic_rtl.html", "nav_trap.html",
])
def test_every_cms_shape_yields_a_listing(name):
    result = extract(fixture(name), base_url="https://donor.example/notices")
    assert len(result.rows) >= 3, f"{name}: {result.layer} {result.quality}"
    assert result.quality >= QUALITY_THRESHOLD, f"{name} won on {result.layer} at {result.quality}"


def test_rss_links_are_not_empty_and_pubdate_is_found():
    """BeautifulSoup's HTML parser treats <link> as void, so feeds must be
    parsed as XML -- and <pubDate> will not match a search for "pubdate"."""
    result = feed_layer(fixture("notices.rss"), base_url="https://donor.example")
    assert len(result.rows) == 3
    assert all(row.url and row.url.startswith("https://donor.example/notice/") for row in result.rows)
    assert all(row.cells.get("date") for row in result.rows)


def test_site_level_jsonld_does_not_become_phantom_notices():
    """Nearly every page embeds {"@type":"Organization", ...}."""
    from syria_monitor.extraction import embedded_json_layer
    soup = BeautifulSoup(fixture("jsonld_site_only.html"), "html.parser")
    titles = {row.title for row in embedded_json_layer(soup).rows}
    assert "Donor Agency" not in titles
    assert "Donor Agency Procurement" not in titles


def test_nextjs_json_is_read():
    result = extract(fixture("nextjs.html"), base_url="https://donor.example")
    assert result.layer == "embedded_json"
    assert any("Latakia" in row.title for row in result.rows)


# ------------------------------------------------------------- the unclosed cell
def test_unclosed_cell_does_not_swallow_the_next_columns():
    """`<td>n.v.<td>10030355 - Studie ...` nests the title and buyer inside the
    deadline cell. find_all still returns the right number of cells in the right
    order and the header still maps correctly -- the row simply comes out with a
    closing date containing the title and the buyer."""
    soup = BeautifulSoup(fixture("giz_header_table.html"), "html.parser")
    row = soup.find_all("tr")[1]
    cells = row.find_all(["td", "th"])
    assert len(cells) == 4, "column count must survive the unclosed tag"
    assert cell_text(cells[1]) == "n.v."
    assert "Studie" in cells[1].get_text(" ", strip=True), "fixture must reproduce the nesting"

    result = table_layer(soup)
    deadline = result.rows[0].cells.get("deadline", "")
    assert deadline == "n.v."
    assert "Studie" not in deadline and "GIZ GmbH" not in deadline


def test_direct_children_would_collapse_the_columns():
    """Documents why the fix is not find_all(recursive=False)."""
    soup = BeautifulSoup(fixture("giz_header_table.html"), "html.parser")
    row = soup.find_all("tr")[1]
    assert len(row.find_all(["td", "th"], recursive=False)) == 2      # collapsed
    assert len(row.find_all(["td", "th"])) == 4                       # correct


def test_german_dates_from_the_table_parse():
    from syria_monitor.dates import parse_date
    from datetime import date
    soup = BeautifulSoup(fixture("giz_header_table.html"), "html.parser")
    rows = table_layer(soup).rows
    assert parse_date(rows[1].cells["deadline"]) == date(2026, 12, 31)
    assert parse_date(rows[2].cells["deadline"]) == date(2027, 1, 15)


# ------------------------------------------------------------- the quality gate
def test_over_broad_selector_does_not_short_circuit_the_working_layer():
    """A bare `nav li` matches navigation. Scoring keeps it from winning."""
    result = extract(fixture("nav_trap.html"), base_url="https://donor.example",
                     selectors={"row": "nav li"})
    titles = " ".join(row.title for row in result.rows)
    assert "Home" not in titles and "About" not in titles
    assert "Aleppo" in titles


def test_related_documents_table_does_not_win_over_the_notice_list():
    result = extract(fixture("nav_trap.html"), base_url="https://donor.example")
    titles = " ".join(row.title for row in result.rows)
    assert "Guidance note" not in titles
    assert "Aleppo" in titles


# --------------------------------------------------- guard clauses that skip work
@pytest.mark.parametrize("size", [50, 500, 2000])
def test_structural_inference_handles_large_listings(size):
    """A "container too large" cap silently returns zero rows on exactly the
    page this layer exists to rescue."""
    html = ("<html><body><div id='x'>" + "".join(
        f"<div><a href='/n/{i}'>Notice {i} water supply, Aleppo</a>"
        f"<span>Deadline: 0{i % 9 + 1}-Sep-2026</span></div>" for i in range(size))
        + "</div></body></html>")
    result = structural_layer(BeautifulSoup(html, "html.parser"))
    assert len(result.rows) == size


# ------------------------------------------------------------------- diagnosis
def test_bot_wall_is_diagnosed_distinctly():
    assert diagnose(fixture("cloudflare_wall.html")).startswith("bot_wall")


def test_js_shell_is_diagnosed_distinctly():
    assert diagnose(fixture("js_shell.html")).startswith("js_shell")


def test_transport_error_is_diagnosed_distinctly():
    assert diagnose("<html><body>Not found</body></html>", status=404).startswith("transport")


def test_plain_layout_change_is_diagnosed_distinctly():
    html = "<html><body><p>" + ("content " * 100) + "</p></body></html>"
    assert diagnose(html, status=200).startswith("layout_change")


def test_a_wall_returns_no_rows_rather_than_junk():
    result = extract(fixture("cloudflare_wall.html"), base_url="https://donor.example")
    assert result.rows == []
    assert result.diagnosis and result.diagnosis.startswith("bot_wall")


def test_arabic_survives_extraction():
    result = extract(fixture("arabic_rtl.html"), base_url="https://donor.example")
    assert any("حلب" in row.title for row in result.rows)
