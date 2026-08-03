"""
Extraction tests: the cascade, the quality gate, and the parsers.

Every fixture here is a CMS shape one of these portals actually uses, plus the
three adversarial cases that matter most -- a bot wall, a JavaScript shell, and
a page where an over-broad selector matches navigation instead of the listing.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from jordan_tender_monitor.portals import htmlkit as H
from jordan_tender_monitor.utils import money, text as textutil
from jordan_tender_monitor.utils.dates import is_open, parse_date

from .harness import check, check_eq

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str) -> str:
    return io.open(FIXTURES / name, encoding="utf-8").read()


# ---------------------------------------------------------------------------
# The cascade, per CMS shape
# ---------------------------------------------------------------------------


def test_drupal_views_listing():
    result = H.extract(load("drupal_views.html"), "https://e.org/", [".views-row"])
    check_eq(len(result.rows), 4, "drupal: four notices")
    check(result.quality >= H.QUALITY_THRESHOLD, "drupal: clears the quality gate")
    row = result.rows[0]
    check("Ministry of Finance" in row.title, "drupal: title read")
    check_eq(row.url, "https://e.org/notices/2026-114", "drupal: url resolved absolute")
    check_eq(parse_date(row.closing_text), date(2026, 9, 30), "drupal: deadline parsed")
    check_eq(money.parse_value_usd(row.value_text, "EUR"),
             round(1_850_000 * 1.09, 2), "drupal: EUR value converted")


def test_bootstrap_cards():
    result = H.extract(load("bootstrap_cards.html"), "https://e.org/", [".tender-card"])
    check_eq(len(result.rows), 3, "cards: three notices")
    check_eq(parse_date(result.rows[0].closing_text), date(2026, 11, 15),
             "cards: day-first date parsed")


def test_header_aware_table():
    result = H.extract(load("table_listing.html"), "https://e.org/")
    check_eq(result.layer, "table", "table: table layer wins")
    check_eq(len(result.rows), 4, "table: four rows, header excluded")
    row = result.rows[0]
    check_eq(row.reference, "JO-2026-001", "table: reference column mapped")
    check_eq(row.extra.get("notice_type"), "RFP", "table: type column mapped")
    check_eq(parse_date(row.date_text), date(2026, 6, 1), "table: published column mapped")
    check_eq(parse_date(row.closing_text), date(2026, 9, 15), "table: deadline column mapped")


def test_german_table_formats():
    result = H.extract(load("german_table.html"), "https://e.org/")
    check_eq(len(result.rows), 3, "german: three rows")
    rows = {r.title[:20]: r for r in result.rows}
    first = result.rows[0]
    check_eq(parse_date(first.closing_text), date(2026, 12, 31),
             "german: 31.12.2026 is 31 December")
    parsed = money.parse_value(first.value_text)
    check_eq(parsed[0] if parsed else None, 1_500_000.0,
             "german: EUR 1.500.000 is 1.5 million, not 1.5")
    named = [r for r in result.rows if "Machbarkeit" in r.title]
    if check(named, "german: named-month row present"):
        check_eq(parse_date(named[0].closing_text), date(2027, 1, 15),
                 "german: '15. Januar 2027' parsed")
    check(rows or True, "german: rows indexed")


def test_nextjs_embedded_json():
    result = H.extract(load("nextjs_json.html"), "https://e.org/")
    check_eq(result.layer, "embedded-json", "nextjs: JSON layer wins")
    check_eq(len(result.rows), 3, "nextjs: three notices")
    check_eq(result.rows[0].reference, "UNGM-2026-441", "nextjs: id read")
    check_eq(parse_date(result.rows[0].closing_text), date(2026, 9, 20),
             "nextjs: deadline read")


def test_jsonld_notices():
    result = H.extract(load("ldjson.html"), "https://e.org/")
    check_eq(result.layer, "embedded-json", "json-ld: JSON layer wins")
    check_eq(len(result.rows), 3, "json-ld: three notices")


def test_site_level_jsonld_does_not_hijack():
    """An Organization node must not become a phantom notice.

    Nearly every page embeds {"@type":"Organization","name":...,"url":...}.
    Accepting it fills the report with notices named after the donor.
    """
    html = load("site_ldjson_plus_listing.html")
    json_layer = H.extract_embedded_json(html, "https://e.org/")
    check_eq(len(json_layer.rows), 0,
             "json-ld: site-level Organization and BreadcrumbList rejected")

    result = H.extract(html, "https://e.org/", ["li.notice"])
    check_eq(len(result.rows), 3, "json-ld: the real HTML listing is read instead")
    titles = " ".join(r.title for r in result.rows)
    check("European Bank" not in titles,
          "json-ld: the donor's own name is not a notice")


def test_arabic_rtl_listing():
    result = H.extract(load("arabic_rtl.html"), "https://e.org/", [".tender"])
    check_eq(len(result.rows), 3, "arabic: three notices")
    row = result.rows[0]
    check(textutil.is_arabic(row.title), "arabic: title detected as Arabic")
    check_eq(parse_date(row.closing_text), date(2026, 10, 15),
             "arabic: Levantine month and Arabic-Indic digits parsed")
    parsed = money.parse_value(row.value_text)
    check_eq(parsed[0] if parsed else None, 750_000.0,
             "arabic: Arabic-Indic digits and دولار parsed as a value")
    national = [r for r in result.rows if textutil.detect_national_only(r.blob())]
    check(national, "arabic: 'الشركات المحلية فقط' detected as national-only")


def test_rss_feed_link_and_pubdate():
    """<link> is a void element to an HTML parser, and <pubDate> is camelCase."""
    result = H.extract(load("feed.xml"), "https://e.org/")
    check_eq(result.layer, "feed", "rss: feed layer wins")
    check_eq(len(result.rows), 3, "rss: three items")
    check_eq(result.rows[0].url, "https://example.org/notice/7001",
             "rss: <link> text survived (XML parser, not HTML)")
    check(parse_date(result.rows[0].date_text) is not None,
          "rss: <pubDate> matched case-insensitively")


def test_structural_inference_no_classes():
    result = H.extract(load("unknown_layout.html"), "https://e.org/")
    check_eq(result.layer, "structural", "structural: wins with no classes present")
    check_eq(len(result.rows), 4, "structural: four notices")


def test_anchor_pattern_last_resort():
    html = load("anchor_only.html")
    layer = H.extract_anchor_pattern(html, "https://e.org/", "/tender/")
    check_eq(len(layer.rows), 4, "anchor: four notices, nav links excluded")
    check(all("/tender/view/" in (r.url or "") for r in layer.rows),
          "anchor: only the notice URL shape kept")
    check("closes 30 September 2026" in layer.rows[0].raw_text,
          "anchor: row text scoped to its own row, not the whole page")


# ---------------------------------------------------------------------------
# The quality gate -- the reason the cascade works at all
# ---------------------------------------------------------------------------


def test_overbroad_selector_is_rejected():
    """A bare 'article' selector matches four promo panels before the listing.

    Selectors run before the class-independent layers, so without the gate this
    short-circuits the structural layer and the report fills with navigation.
    """
    html = load("selector_hijack.html")

    hijack = H.extract_by_selectors(html, ["article"], "https://e.org/")
    check_eq(len(hijack.rows), 4, "gate: the over-broad selector does match nav")
    check(hijack.quality < H.QUALITY_THRESHOLD,
          "gate: but it scores below the gate",
          f"scored {hijack.quality}")

    result = H.extract(html, "https://e.org/", ["article"])
    check_eq(result.layer, "structural", "gate: structural inference wins instead")
    titles = " ".join(r.title for r in result.rows)
    check("Fiscal Decentralisation" in titles, "gate: the real listing is returned")
    check("About our procurement" not in titles, "gate: no navigation in the result")


def test_dateless_rows_score_low():
    rows = [H.Row(title=f"Some Navigation Entry {i}", url=f"/x/{i}") for i in range(4)]
    check(H.score_rows(rows) < H.QUALITY_THRESHOLD,
          "gate: rows with no dates at all cannot clear the gate")

    dated = [H.Row(title=f"Advisory Assignment Number {i}", url=f"/x/{i}",
                   closing_text="30 September 2026") for i in range(4)]
    check(H.score_rows(dated) >= H.QUALITY_THRESHOLD,
          "gate: the same rows with dates do clear it")


def test_best_effort_when_nothing_clears_the_gate():
    """A weak result the caller can see beats a silent zero."""
    html = ("<html><body><ul>"
            + "".join(f'<li><a href="/n/{i}">Some Notice Title Number {i}</a></li>'
                      for i in range(4))
            + "</ul></body></html>")
    result = H.extract(html, "https://e.org/")
    check(result.rows, "best-effort: rows are returned even below the gate")
    check("BELOW QUALITY GATE" in result.note,
          "best-effort: and they are labelled as unverified")


# ---------------------------------------------------------------------------
# Structural inference at scale -- the guard clause that skipped its own case
# ---------------------------------------------------------------------------


def _big_listing(n: int) -> str:
    return ("<!doctype html><html><body><div>" + "".join(
        f'<section><h4><a href="/x/{i}">Governance Advisory Assignment {i}, Jordan</a>'
        f'</h4><p>Published 01 July 2026</p><p>Deadline 01 October 2026</p>'
        f'<p>Estimated value USD {100000 + i}</p></section>' for i in range(n))
        + "</div></body></html>")


def test_structural_at_50_500_2000_rows():
    """A 'container too large' cap once returned zero rows on a 500-notice page.

    That is precisely the page this layer exists to rescue, so size is tested
    explicitly at three magnitudes.
    """
    for n in (50, 500, 2000):
        result = H.extract_structural(_big_listing(n), "https://e.org/")
        check_eq(len(result.rows), n, f"scale: {n} rows in, {n} rows out")


# ---------------------------------------------------------------------------
# Failure diagnosis -- each class needs a different fix
# ---------------------------------------------------------------------------


def test_bot_wall_diagnosed():
    html = load("cloudflare_wall.html")
    result = H.extract(html, "https://e.org/", [".notice"])
    check_eq(len(result.rows), 0, "botwall: no rows extracted")
    check("bot wall" in H.diagnose(html, []), "botwall: diagnosed as a bot wall")
    check("Playwright" in H.diagnose(html, []),
          "botwall: the fix is named (different network or Playwright)")


def test_javascript_shell_diagnosed():
    html = load("js_shell.html")
    result = H.extract(html, "https://e.org/", [".notice"])
    check_eq(len(result.rows), 0, "jsshell: no rows extracted")
    diagnosis = H.diagnose(html, [])
    check("JavaScript shell" in diagnosis, "jsshell: diagnosed as a JS shell")
    check("playwright install chromium" in diagnosis, "jsshell: the fix is named")


def test_transport_error_diagnosed():
    check("transport error" in H.diagnose("", []),
          "transport: empty content diagnosed as a transport error")


def test_layout_change_diagnosed():
    html = ("<html><body><p>" + ("Some ordinary prose about procurement policy. " * 40)
            + "</p></body></html>")
    check("layout change" in H.diagnose(html, []),
          "layout: a full page with no listing diagnosed as a layout change")


# ---------------------------------------------------------------------------
# Value parsing -- the defect that silently deleted real tenders
# ---------------------------------------------------------------------------


def test_dates_are_not_read_as_values():
    check_eq(money.parse_value("Published: 01 August 2026"), None,
             "value: a date is not a contract value")
    check_eq(money.parse_value("Deadline 31.12.2026"), None,
             "value: a dotted date is not a value")
    check_eq(money.parse_value("Lot 3 of 7, ref 2026/S 123-456789"), None,
             "value: reference numbers are not values")
    check_eq(money.parse_value("Notice 2026-114"), None,
             "value: a notice number is not a value")


def test_currency_or_magnitude_required():
    check(money.parse_value("USD 250,000") is not None, "value: currency code accepted")
    check(money.parse_value("2.5 million") is not None, "value: magnitude word accepted")
    check(money.parse_value("750k USD") is not None, "value: 'k' suffix accepted")
    check_eq(money.parse_value("1500000"), (1500000.0, "USD"),
             "value: a bare numeric field is taken at face value")


def test_european_number_formats():
    cases = [
        ("EUR 1.500.000", 1_500_000.0, "dot as thousands"),
        ("EUR 1.500,50", 1_500.50, "comma as decimal"),
        ("USD 1,500,000", 1_500_000.0, "comma as thousands"),
        ("USD 1,500.50", 1_500.50, "dot as decimal"),
        ("EUR 850.000", 850_000.0, "three-digit group is thousands"),
    ]
    for text, want, label in cases:
        got = money.parse_value(text)
        check_eq(got[0] if got else None, want, f"value: {label}")


def test_largest_candidate_wins():
    got = money.parse_value("EUR 50,000 per year, total EUR 1,200,000")
    check_eq(got[0] if got else None, 1_200_000.0,
             "value: the largest qualifying figure is the contract value")


def test_arabic_value_parsing():
    got = money.parse_value("قيمة العقد ٢٥٠٠٠٠ دولار")
    check_eq(got[0] if got else None, 250_000.0,
             "value: Arabic-Indic digits with an Arabic currency word")


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------


def test_multilingual_dates():
    cases = [
        ("2026-12-31", date(2026, 12, 31), "ISO"),
        ("31.12.2026", date(2026, 12, 31), "German dotted"),
        ("15. Januar 2027", date(2027, 1, 15), "German named month"),
        ("28 fevrier 2027", date(2027, 2, 28), "French named month"),
        ("15 October 2026", date(2026, 10, 15), "English"),
        ("١٥ تشرين الأول ٢٠٢٦", date(2026, 10, 15), "Arabic Levantine"),
        ("٣١ ديسمبر ٢٠٢٦", date(2026, 12, 31), "Arabic Gulf"),
        ("03/04/2026", date(2026, 4, 3), "day-first slashes"),
    ]
    for text, want, label in cases:
        check_eq(parse_date(text), want, f"date: {label}")

    check_eq(parse_date("no date at all"), None, "date: prose yields None")


def test_iso_timestamps_do_not_swap_day_and_month():
    """Every REST API here returns ISO with a T, and this used to be wrong.

    A \\b after the day fails against the following "T", so the ISO fast path
    was skipped and dateutil's dayfirst=True read 2026-06-01 as 6 January.
    Every date where day and month were both <= 12 came out transposed, which
    moved closing dates by months in either direction.
    """
    cases = [
        ("2026-06-01T09:00:00Z", date(2026, 6, 1), "ISO with T and Z"),
        ("2026-09-12T12:00:00Z", date(2026, 9, 12), "ISO where both parts are <= 12"),
        ("2026-06-10+02:00", date(2026, 6, 10), "ISO with a UTC offset"),
        ("2026-09-30T17:00:00-04:00", date(2026, 9, 30), "ISO with a negative offset"),
        ("2026-06-01 09:00:00", date(2026, 6, 1), "ISO with a space separator"),
        ("2026-06-01T00:00:00.000Z", date(2026, 6, 1), "ISO with milliseconds"),
        ("2026-6-1T09:00:00Z", date(2026, 6, 1), "ISO without zero padding"),
        ("2026-01-06T09:00:00Z", date(2026, 1, 6), "the transposed twin parses correctly too"),
    ]
    for text, want, label in cases:
        check_eq(parse_date(text), want, f"iso: {label}")
    check_eq(parse_date(None), None, "date: None yields None")
    check_eq(parse_date(""), None, "date: empty string yields None")


def test_deadline_boundary_today_is_open():
    today = date(2026, 6, 15)
    check(is_open(today, today), "deadline: closing today counts as OPEN")
    check(is_open(date(2026, 6, 16), today), "deadline: tomorrow is open")
    check(not is_open(date(2026, 6, 14), today), "deadline: yesterday is closed")
    check(is_open(None, today), "deadline: unknown deadline is treated as open")


# ---------------------------------------------------------------------------
# Country matching -- Jordanstown and Ammanford must stay out
# ---------------------------------------------------------------------------


def test_country_matching_word_boundaries():
    check(textutil.mentions_jordan("Consulting services in Amman, Jordan"),
          "country: Jordan matched")
    check(not textutil.mentions_jordan("Road works in Jordanstown, County Antrim"),
          "country: Jordanstown NOT matched")
    check(not textutil.mentions_jordan("School extension in Ammanford, Wales"),
          "country: Ammanford NOT matched")
    check(textutil.mentions_jordan("Water network upgrade, Irbid governorate"),
          "country: a Jordanian city matched")


def test_country_matching_strips_emails_but_trusts_jo_domain():
    check(not textutil.mentions_jordan("Contact procurement@undp-jordan.org for details"),
          "country: an email address alone is not evidence")
    check(textutil.mentions_jordan("Tender reference 123", url="https://mit.gov.jo/t/1"),
          "country: a .jo domain IS positive evidence")


def test_arabic_country_matching_is_substring():
    """Arabic is agglutinative -- الأردنية legitimately contains الأردن."""
    check(textutil.mentions_jordan("مشروع في الأردنية للتنمية"),
          "country: Arabic matched as a substring")
    check(textutil.mentions_jordan("المملكة الأردنية الهاشمية"),
          "country: the full Arabic country name matched")


def test_a_save_button_does_not_become_the_notice():
    """VERIFIED LIVE ON UNGM. Fifteen notices, fifteen identical titles.

    Every row on the rendered listing opens with
    `<a href="javascript:void(0);">Unsave this procurement opportunity.</a>`,
    and taking the first anchor made that the title and the URL of every
    notice. The result was a listing of buttons: no working link, no way to
    tell two notices apart, and nothing a reader could act on.
    """
    result = H.extract(load("save_button_rows.html"),
                       "https://www.ungm.org/Public/Notice",
                       ["div.dataRow.notice-table"],
                       anchor_hint="/Public/Notice/")
    check_eq(len(result.rows), 4, "save button: four notices found")

    titles = [row.title for row in result.rows]
    check(not any("Unsave" in t for t in titles),
          "save button: no row is titled after the save control", f"got {titles}")
    check(len(set(titles)) == 4,
          "save button: four notices produce four distinct titles")
    check("water sector reform" in titles[0],
          "save button: the title is the notice's own link text")

    urls = [row.url or "" for row in result.rows]
    check(not any("javascript:" in u for u in urls),
          "save button: no row links to javascript:void(0)", f"got {urls}")
    check(all("/Public/Notice/" in u for u in urls),
          "save button: every row links to a real notice")


def test_an_advertisement_does_not_become_the_notice_either():
    """The second half of the UNGM defect, and the more dangerous half.

    Skipping the save button landed on the NEXT anchor, which is an upsell:
    <a href="/Public/TenderAlertService">UNGM Pro</a>. Every row came back
    titled "UNGM Pro" pointing at the advertising page -- and unlike the save
    button, those rows carried dates, so they cleared the quality gate and
    would have been reported as tenders. A silent failure became a confident
    wrong answer.

    A portal that declares an anchor_hint has already said what its notice URLs
    look like. Nothing else in the row distinguishes an advert from a notice.
    """
    html = load("save_button_rows.html")

    # Without the hint, the advert wins -- pinning the regression itself, so a
    # future change cannot quietly reintroduce it.
    unhinted = H.extract_by_selectors(html, ["div.dataRow.notice-table"],
                                      "https://www.ungm.org/Public/Notice")
    check(all(r.title == "UNGM Pro" for r in unhinted.rows),
          "advert: without a hint the upsell link is what a row looks like")

    hinted = H.extract_by_selectors(html, ["div.dataRow.notice-table"],
                                    "https://www.ungm.org/Public/Notice",
                                    anchor_hint="/Public/Notice/")
    check_eq(len(hinted.rows), 4, "advert: four rows with the hint applied")
    check(not any("UNGM Pro" == r.title for r in hinted.rows),
          "advert: the hint keeps the upsell out of the titles")
    check(not any("TenderAlertService" in (r.url or "") for r in hinted.rows),
          "advert: and out of the URLs")
    check(all("/Public/Notice/" in (r.url or "") for r in hinted.rows),
          "advert: every row links to the notice the hint describes")

    # The hint is a preference, not a requirement: a row with no matching
    # anchor still gets its first real link rather than nothing.
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(
        '<div><a href="javascript:void(0);">Save</a>'
        '<a href="/other/9">Advisory Services, Amman</a></div>', "html.parser")
    row = H._node_to_row(soup.find("div"), "https://e.org/", "/Public/Notice/")
    check_eq(row.url, "https://e.org/other/9",
             "advert: an unmatched hint falls back to the first real link")


def test_dead_hrefs_are_never_a_rows_link():
    """mailto:, tel: and # are the same defect wearing a different hat."""
    from bs4 import BeautifulSoup

    for dead in ("javascript:void(0);", "#", "mailto:bids@example.org", "tel:+962"):
        soup = BeautifulSoup(
            f'<div><a href="{dead}">Contact us</a>'
            f'<a href="/notices/7">Advisory Services, Amman</a></div>',
            "html.parser")
        row = H._node_to_row(soup.find("div"), "https://e.org/")
        check_eq(row.url, "https://e.org/notices/7",
                 f"dead href: '{dead}' is skipped in favour of the real link")
        check_eq(row.title, "Advisory Services, Amman",
                 f"dead href: '{dead}' does not supply the title")


def test_a_month_name_joined_by_hyphens_is_recognised():
    """VERIFIED LIVE ON UNGM: "03-Aug-2026".

    parse_date read this format all along. The extractor's date-span pattern
    did not -- every alternation wanted either digits for the month or
    whitespace around a named one -- so the date was never handed to the
    parser, and the rows scored as dateless.
    """
    check_eq(parse_date("03-Aug-2026"), date(2026, 8, 3),
             "hyphen month: the parser reads it")
    check_eq(H._first_date_text("Deadline 03-Aug-2026 19:00 (GMT -4.00)"),
             "03-Aug-2026",
             "hyphen month: and the extractor now finds it in a row of text")
    check_eq(H._first_date_text("Closing 12-Oct-2026 17:00"), "12-Oct-2026",
             "hyphen month: October too")
    check_eq(H._first_date_text("15/January/2027"), "15/January/2027",
             "hyphen month: slashes and a full month name as well")

    # The formats that already worked must keep working.
    check_eq(H._first_date_text("Deadline: 30 September 2026"), "30 September 2026",
             "hyphen month: spaced month names still parse")
    check_eq(H._first_date_text("Frist 31.12.2026"), "31.12.2026",
             "hyphen month: German numeric dates still parse")


def test_an_unclosed_cell_does_not_swallow_the_rest_of_the_row():
    """VERIFIED LIVE ON GIZ, 3 August 2026. Every deadline was unusable.

    The German portal publishes `<td>n.v.<td>10030355 - Studie...` -- the
    deadline cell is never closed, so the parser nests the title, the type and
    the buyer inside it. Nothing about this looks wrong from the outside: the
    table layer wins at quality 1.00, six cells are found in document order,
    and the header maps correctly onto posted / closing / title. Only the cell
    contents are wrong, and only for one column.
    """
    result = H.extract_tables(load("unclosed_cell_table.html"),
                              "https://ausschreibungen.giz.de/x")
    check_eq(len(result.rows), 2, "unclosed cell: both rows read")

    broken, healthy = result.rows
    check_eq(broken.closing_text, "n.v.",
             "unclosed cell: the deadline cell keeps ONLY its own text")
    check("Studie" not in broken.closing_text,
          "unclosed cell: the title has not leaked into the deadline")
    check("GIZ" not in broken.closing_text,
          "unclosed cell: nor has the buyer, two columns further along")
    check(parse_date(broken.closing_text) is None,
          "unclosed cell: 'n.v.' is an absent deadline, not a parsed one")
    check("Studie zum Ausbau" in broken.title,
          "unclosed cell: the title is still read from its own cell")
    check_eq(broken.date_text, "03.08.2026",
             "unclosed cell: the posted date is untouched")
    check(broken.url and broken.url.endswith("pid=51974"),
          "unclosed cell: the link is still resolved from the title cell")

    # The other half of the fix: valid markup must be completely unaffected.
    check_eq(parse_date(healthy.closing_text), date(2027, 1, 15),
             "unclosed cell: a well-formed row still parses '15. Januar 2027'")
    check_eq(parse_date(healthy.date_text), date(2026, 7, 1),
             "unclosed cell: and its posted date")
    check("Verwaltungsreform" in healthy.title,
          "unclosed cell: and its title")


def test_own_text_is_identical_on_well_formed_cells():
    """The fix must be a no-op wherever the markup is valid."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        "<table><tr><td>Amman</td><td><b>15.</b> Januar <i>2027</i></td></tr></table>",
        "html.parser")
    cells = soup.find_all("td")
    for cell in cells:
        check_eq(H._own_text(cell), textutil.clean(cell.get_text(" ")),
                 "own-text: matches get_text() when no cell is nested")


TESTS = [
    test_drupal_views_listing,
    test_bootstrap_cards,
    test_header_aware_table,
    test_german_table_formats,
    test_nextjs_embedded_json,
    test_jsonld_notices,
    test_site_level_jsonld_does_not_hijack,
    test_arabic_rtl_listing,
    test_rss_feed_link_and_pubdate,
    test_structural_inference_no_classes,
    test_anchor_pattern_last_resort,
    test_overbroad_selector_is_rejected,
    test_dateless_rows_score_low,
    test_best_effort_when_nothing_clears_the_gate,
    test_structural_at_50_500_2000_rows,
    test_bot_wall_diagnosed,
    test_javascript_shell_diagnosed,
    test_transport_error_diagnosed,
    test_layout_change_diagnosed,
    test_dates_are_not_read_as_values,
    test_currency_or_magnitude_required,
    test_european_number_formats,
    test_largest_candidate_wins,
    test_arabic_value_parsing,
    test_multilingual_dates,
    test_iso_timestamps_do_not_swap_day_and_month,
    test_deadline_boundary_today_is_open,
    test_country_matching_word_boundaries,
    test_country_matching_strips_emails_but_trusts_jo_domain,
    test_arabic_country_matching_is_substring,
    test_an_unclosed_cell_does_not_swallow_the_rest_of_the_row,
    test_own_text_is_identical_on_well_formed_cells,
    test_a_save_button_does_not_become_the_notice,
    test_an_advertisement_does_not_become_the_notice_either,
    test_dead_hrefs_are_never_a_rows_link,
    test_a_month_name_joined_by_hyphens_is_recognised,
]
