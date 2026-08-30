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


def test_an_icon_anchor_before_the_title_does_not_eat_the_row():
    """UNGM renders a save-this-notice icon anchor before the notice link.

    Observed live on 2026-08-30: the markup held 15 notice rows and the cascade
    reported 6. Taking node.find("a") -- the FIRST anchor -- meant the title
    came from an icon with no text and the URL from its href="#". Empty titles
    are dropped, which wiped the whole group and let a group of table *cells*
    win instead: fifteen notices became four rows titled "30-Sep-2026",
    "29-Jul-2026" and "UNDP".

    That is the failure worth a regression test. An empty result invites
    questions; a plausible-looking listing of the wrong thing does not.
    """
    from bs4 import BeautifulSoup
    from syria_monitor.extraction import structural_layer

    def row(index):
        return (
            '<div class="tableRow"><div class="dataRow">'
            '<div class="tableCell">'
            '<a class="save-notice-button" href="#"><svg></svg></a></div>'
            f'<div class="tableCell"><a href="/Public/Notice/{309000 + index}">'
            f'Rehabilitation of water network, site {index}</a></div>'
            '<div class="tableCell">30-Sep-2026</div>'
            '<div class="tableCell">29-Jul-2026</div>'
            '<div class="tableCell">UNDP</div>'
            '<div class="tableCell">Syrian Arab Republic</div>'
            '</div></div>')

    html = "<div class='notice-table'>" + "".join(row(i) for i in range(15)) + "</div>"
    result = structural_layer(BeautifulSoup(html, "html.parser"), "https://www.ungm.org")

    assert len(result.rows) == 15, "every row in the markup, not a subset"
    assert all("Rehabilitation" in r.title for r in result.rows), \
        "titles come from the anchor that has text, not the icon"
    assert all((r.url or "").startswith("https://www.ungm.org/Public/Notice/")
               for r in result.rows), "the notice link, never the icon's href"


def test_a_row_whose_only_anchor_goes_nowhere_gets_no_url():
    """`#` and javascript: are buttons, not links.

    Rendering one as a notice's URL sends the reader nowhere and says nothing
    about it. The report writer promises a clickable link or a stated reason
    for its absence, and a dead href satisfies neither.
    """
    from bs4 import BeautifulSoup
    from syria_monitor.extraction import _rows_from_group

    html = "<div>" + "".join(
        '<div class="r"><a href="#"><svg></svg></a>'
        '<span>Water supply works, Aleppo — closes 30-Sep-2026</span></div>'
        for _ in range(4)) + "</div>"
    nodes = BeautifulSoup(html, "html.parser").select("div.r")
    rows = _rows_from_group(nodes, "https://example.test")

    assert rows[0].url is None, "a dead href is worse than no href"
    assert "Water supply works" in rows[0].title, "title falls back to the node's text"


def _ungm_shaped_rows(count=15):
    """Rows sharing a class but NOT siblings of one another.

    The live shape from issue #56: `div.tableRow x15` in the markup and no
    structural candidate above six. Each row sits under its own wrapper, and
    the wrappers differ in shape, so no parent holds three similar children.
    """
    out = []
    for i in range(count):
        extra = ["<span>ad</span>", "<p>promo</p>", "<a href='/x'>more</a>"][i % 3]
        out.append(
            f'<section><div class="notice-table"><div class="tableRow">'
            f'<div class="tableCell"><a class="save" href="#"><svg></svg></a></div>'
            f'<div class="tableCell"><a href="/Public/Notice/{309000 + i}">'
            f'Provision of equipment for site {i}, Aleppo</a></div>'
            f'<div class="tableCell">closes 30-Sep-2026</div>'
            f'<div class="tableCell">UNDP</div>'
            f'<div class="tableCell">Syrian Arab Republic</div>'
            f'</div></div>{extra}</section>')
    return "<html><body><main>" + "".join(out) + "</main></body></html>"


def test_rows_that_share_a_class_are_found_even_when_they_are_not_siblings():
    """Issue #56, the case structural cannot reach.

    structural_layer groups direct siblings. UNGM's rows are not siblings of
    one another, so they never formed a candidate at all -- the layer reported
    on six `div>span` blocks, the cells inside one row, and the report carried
    a tender titled "Syrian Arab Republic" with a score of 0.

    A page that repeats a class fifteen times is telling you what its rows are.
    """
    from syria_monitor.extraction import extract

    result = extract(_ungm_shaped_rows(), "https://www.ungm.org")

    assert len(result.rows) == 15, "every row, not the cells of one row"
    assert all("Provision of equipment" in r.title for r in result.rows)
    assert all((r.url or "").startswith("https://www.ungm.org/Public/Notice/")
               for r in result.rows), "the notice link, not the save-icon's href"


def test_a_navigation_menu_is_not_accepted_as_a_listing():
    """The failure the class-aware layer is most likely to cause.

    A nav menu repeats its class more consistently than any listing does, so
    class repetition ALONE would hand the page to the navigation -- the exact
    trap structural_layer's docstring warns about. The quality gate is what
    separates them, and this asserts on `wins`, not on row count: finding the
    items is fine, accepting them as tenders is not.
    """
    from syria_monitor.extraction import extract

    items = "".join(
        f'<li class="nav"><a class="nav-content" href="/section/{i}">Section {i}</a>'
        f'<ul class="nav-children"><li class="nav">'
        f'<a class="nav-content" href="/section/{i}/sub">Sub {i}</a></li></ul></li>'
        for i in range(20))
    html = f"<html><body><nav><ul>{items}</ul></nav><p>No notices today.</p></body></html>"

    result = extract(html, "https://x.test")

    assert not any(a.wins for a in result.attempts), \
        "no layer may accept a nav menu as a listing"
    assert result.quality < 0.45, "below the bar, whatever the row count"


def test_the_repeated_class_layer_does_not_count_a_nested_class_twice():
    """A wrapper class used at two depths must not double the listing.

    Counting the same notice twice does not look like a bug -- it looks like a
    fuller listing, which is the shape of failure this project keeps meeting.
    """
    from bs4 import BeautifulSoup
    from syria_monitor.extraction import repeated_class_layer

    inner = "".join(
        f'<div class="box"><a href="/n/{i}">Water works, Homs {i}</a>'
        f'<span>closes 30-Sep-2026</span></div>' for i in range(4))
    # Same class on an outer wrapper as on each row.
    html = f'<div class="box">{inner}</div>'

    result = repeated_class_layer(BeautifulSoup(html, "html.parser"), "https://x.test")
    titles = [r.title for r in result.rows]
    assert len(titles) == len(set(titles)), f"duplicated rows: {titles}"


def test_a_save_button_with_text_does_not_become_the_title():
    """The live shape, which the first correction's fixture did not model.

    UNGM's save-notice control is an anchor with href="#" AND an accessible
    label. Preferring "the first anchor with text" therefore picked it, and the
    run of 2026-08-30 reported every notice as "Unsave this procurement
    opportunity." -- a plausible-looking listing of the wrong thing, which is
    the failure mode this module is most concerned with.

    The fixture that vetted the previous fix rendered the button as
    `<a href="#"><svg></svg></a>`, with no text, which is the single shape
    where the bug cannot reproduce.
    """
    rows = "".join(
        '<div class="dataRow notice-table">'
        '<a class="save-notice-button" href="#">'
        'Unsave this procurement opportunity. Subscribe to UNGM Pro to be able to save.'
        '</a>'
        f'<a class="ungm-title" href="/Public/Notice/{200 + i}">Supply of medical equipment, lot {i}</a>'
        f'<span>0{i}-Sep-2026</span><span>Syrian Arab Republic</span>'
        '</div>'
        for i in range(1, 8)
    )
    result = extract(f"<html><body><div>{rows}</div></body></html>",
                     base_url="https://www.ungm.org")

    assert len(result.rows) == 7, f"all seven rows, got {len(result.rows)}"
    assert all(r.title.startswith("Supply of medical equipment") for r in result.rows), \
        f"the notice link is the title, not the save button: {[r.title for r in result.rows]}"
    assert not any("Unsave" in r.title for r in result.rows), \
        "the save button's label must never reach a title"
    assert all(r.url and "/Public/Notice/" in r.url for r in result.rows), \
        "the URL is the notice link, never the button's href='#'"


def test_a_month_has_to_be_a_month():
    """The scanner accepted any word of three or more letters as a month.

    "10 Sub 10" is then a date shape, so a navigation menu of "Section 10 /
    Sub 10" items looks half-dated. A four-digit year was masking it: loosening
    the year to two digits -- which UNDP needs -- took the nav fixture from
    quality 0.35 to 0.57 and accepted a menu as a listing. Caught by that
    fixture, which is what it is for.
    """
    from syria_monitor.dates import _DATE_SHAPED

    for junk in ("Section 10 Sub 10", "10 Sub 10", "3 Lot 12", "1 of 11"):
        assert not _DATE_SHAPED.search(junk), f"read {junk!r} as a date"


def test_two_digit_years_are_seen_by_the_scanner():
    """UNDP writes "Deadline 01-Sep-26". The scanner required four digits, so
    it never saw the date, find_labelled_date returned None, and every UNDP
    notice reached the report with no closing date -- while parse_date could
    read the very same string."""
    from syria_monitor.dates import _DATE_SHAPED, find_labelled_date, parse_date
    from datetime import date

    assert _DATE_SHAPED.search("01-Sep-26 09:20 AM (New York time)")
    assert parse_date("01-Sep-26") == date(2026, 9, 1)
    assert find_labelled_date(
        "Deadline 01-Sep-26 09:20 AM (New York time) Posted 29-Aug-26"
    ) == date(2026, 9, 1)


def test_the_shapes_that_already_worked_still_work():
    """The month vocabulary must not cost the formats the portals already use.

    EVERY MONTH, IN FULL AND ABBREVIATED. The first version of this test
    checked "September 1, 2026" and passed -- September is spelled the same in
    English, German and Dutch, so it is in MONTHS by accident of spelling. The
    English months that are NOT spelled like their German or French
    counterparts were all broken, "15 January 2026" among them, and IsDB's
    reading fell from 50 rows to 3 before anyone noticed. A test that samples
    one month is a test that samples the one month that works.
    """
    from syria_monitor.dates import _DATE_SHAPED

    english = ("January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December")
    for month in english:
        for form in (f"15 {month} 2026", f"15 {month[:3]} 2026",
                     f"15-{month[:3]}-2026", f"{month} 15, 2026"):
            assert _DATE_SHAPED.search(form), f"stopped seeing {form!r}"

    # The languages MONTHS exists for, abbreviated as those sources write them.
    for good in ("15 janvier 2026", "15 janv 2026", "15 févr 2026",
                 "15 juil 2026", "15 déc 2026", "15 Januar 2027",
                 "15 Okt 2026", "15 Mär 2026", "15 يناير 2026"):
        assert _DATE_SHAPED.search(good), f"stopped seeing {good!r}"

    # And the numeric shapes, which never depended on the vocabulary.
    for good in ("30-Aug-2026", "01-Sep-26", "2026-11-02", "31.12.2026"):
        assert _DATE_SHAPED.search(good), f"stopped seeing {good!r}"
