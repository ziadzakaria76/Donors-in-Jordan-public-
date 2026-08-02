"""
Agent 3 -- report builder.

Produces the HTML email body (report format C: full details per tender) plus the
Excel / JSON / CSV / HTML output files.

Every email opens with the same summary block: scan time, portals checked with
tick or cross, raw tender count, post-filter count, and the top 3 by score.
"""

from __future__ import annotations

import csv
import html
import json
import logging
from datetime import datetime
from pathlib import Path

import config

log = logging.getLogger(__name__)

EXCEL_COLUMNS = [
    "Rank", "Title", "Portal", "Sector", "Type", "Posted", "Deadline",
    "Value (USD)", "Score", "Eligibility", "Contact", "Link",
]


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _esc(value) -> str:
    return html.escape(str(value)) if value not in (None, "") else ""


def _fmt_value(value) -> str:
    if value in (None, ""):
        return "Not published"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_date(value, fallback: str = "Not published") -> str:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(str(value)).strftime("%d %b %Y")
    except ValueError:
        return str(value)


def _deadline_text(tender: dict) -> str:
    text = _fmt_date(tender.get("closing_date"), "Not published - verify on portal")
    days = tender.get("days_to_deadline")
    if isinstance(days, int) and days >= 0:
        text += f" ({days} day{'s' if days != 1 else ''} left)"
    return text


def _score_rgb(score: float) -> str:
    """Bare aRGB hex (no '#') -- the form openpyxl requires."""
    if score >= 70:
        return config.COLOR_HIGH
    if score >= 40:
        return config.COLOR_MEDIUM
    return config.COLOR_LOW


def _score_colour(score: float) -> str:
    """CSS colour for the HTML email."""
    return f"#{_score_rgb(score)}"


def _row_of(tender: dict) -> list:
    return [
        tender.get("rank"),
        tender.get("title"),
        tender.get("portal"),
        tender.get("sector") or "Unclassified",
        tender.get("notice_type") or "",
        _fmt_date(tender.get("posted_date"), ""),
        _fmt_date(tender.get("closing_date"), ""),
        tender.get("estimated_value_usd"),
        tender.get("score"),
        tender.get("eligibility_flag") or tender.get("eligibility") or "",
        tender.get("contact") or "",
        tender.get("url") or "",
    ]


# --------------------------------------------------------------------------
# Email body
# --------------------------------------------------------------------------
def _summary_html(statuses: list[dict], stats: dict, scan_time: datetime) -> str:
    rows = []
    for status in statuses:
        if status["ok"]:
            mark = '<span style="color:#107C10;font-weight:bold">&#10004;</span>'
            detail = f"{status['count']} notice(s) &middot; {status['seconds']}s"
        else:
            mark = '<span style="color:#C00000;font-weight:bold">&#10008;</span>'
            detail = (
                f"<span style='color:#C00000'>unavailable - check manually</span><br>"
                f"<span style='color:#666;font-size:11px'>{_esc(status['error'])}</span>"
            )
        rows.append(
            f"<tr><td style='padding:3px 10px 3px 0'>{mark}</td>"
            f"<td style='padding:3px 12px 3px 0'><b>{_esc(status['name'])}</b></td>"
            f"<td style='padding:3px 0;font-size:12px'>{detail}</td></tr>"
        )

    ok_count = sum(1 for s in statuses if s["ok"])
    return f"""
    <div style="background:#F3F6F9;border-left:4px solid #00338D;padding:14px 18px;margin-bottom:22px">
      <h2 style="margin:0 0 10px;font-size:16px;color:#00338D">Scan summary</h2>
      <table style="border-collapse:collapse;font-size:13px">
        <tr><td style="padding:2px 14px 2px 0"><b>Scan completed</b></td>
            <td>{scan_time.strftime('%d %b %Y, %H:%M')} (container local time)</td></tr>
        <tr><td style="padding:2px 14px 2px 0"><b>Portals checked</b></td>
            <td>{ok_count} of {len(statuses)} reachable</td></tr>
        <tr><td style="padding:2px 14px 2px 0"><b>Raw tenders scraped</b></td>
            <td>{stats.get('raw', 0)}</td></tr>
        <tr><td style="padding:2px 14px 2px 0"><b>After filtering</b></td>
            <td>{stats.get('final', 0)} matched
                ({stats.get('duplicates_merged', 0)} duplicate(s) merged)</td></tr>
        <tr><td style="padding:2px 14px 2px 0"><b>Flagged</b></td>
            <td>{stats.get('national_only', 0)} national-only &middot;
                {stats.get('arabic', 0)} Arabic-language</td></tr>
      </table>
      <h3 style="margin:14px 0 6px;font-size:14px;color:#00338D">Portal status</h3>
      <table style="border-collapse:collapse">{''.join(rows)}</table>
    </div>
    """


def _top3_html(tenders: list[dict]) -> str:
    if not tenders:
        return ""
    items = []
    for tender in tenders[:3]:
        items.append(
            f"<li style='margin-bottom:6px'>"
            f"<b>{_esc(tender['title'])}</b><br>"
            f"<span style='font-size:12px;color:#444'>"
            f"{_esc(tender['portal'])} &middot; score {tender['score']} &middot; "
            f"closes {_esc(_deadline_text(tender))}</span></li>"
        )
    return (
        "<div style='margin-bottom:22px'>"
        "<h2 style='font-size:16px;color:#00338D;margin:0 0 8px'>Top 3 by score</h2>"
        f"<ol style='margin:0;padding-left:20px'>{''.join(items)}</ol></div>"
    )


def _flags_html(tender: dict) -> str:
    chips = []
    if tender.get("eligibility_flag"):
        chips.append(("#C00000", "#FDE7E9", tender["eligibility_flag"]))
    if tender.get("language_flag"):
        chips.append(("#8A6D00", "#FFF4CE", tender["language_flag"]))
    if tender.get("deadline_flag"):
        chips.append(("#5C5C5C", "#EFEFEF", tender["deadline_flag"]))
    if tender.get("duplicate_note"):
        chips.append(("#00338D", "#E8EEF7", tender["duplicate_note"]))
    if not chips:
        return ""
    return "".join(
        f"<span style='display:inline-block;background:{bg};color:{fg};"
        f"font-size:11px;padding:2px 8px;border-radius:10px;margin:0 6px 4px 0'>"
        f"{_esc(text)}</span>"
        for fg, bg, text in chips
    )


def _detail_block(tender: dict) -> str:
    """Format C -- every field for one tender."""
    description = tender.get("description") or ""
    if len(description) > config.DESCRIPTION_CHAR_LIMIT:
        description = description[: config.DESCRIPTION_CHAR_LIMIT].rstrip() + " [...]"

    fields = [
        ("Portal", tender.get("portal")),
        ("Notice type", tender.get("notice_type") or "Not stated"),
        ("Sector (inferred)", tender.get("sector") or "Unclassified"),
        ("Posted", _fmt_date(tender.get("posted_date"), "Not published")),
        ("Deadline", _deadline_text(tender)),
        ("Estimated value", _fmt_value(tender.get("estimated_value_usd"))),
        ("Eligibility", tender.get("eligibility") or "Not stated in notice"),
        ("Contact", tender.get("contact") or "See notice"),
        ("Language", "Arabic" if tender.get("language") == "ar" else "English"),
        ("Relevance score", f"{tender.get('score')} / 100"),
    ]
    rows = "".join(
        f"<tr><td style='padding:3px 14px 3px 0;color:#555;white-space:nowrap;"
        f"vertical-align:top'>{label}</td>"
        f"<td style='padding:3px 0'>{_esc(value)}</td></tr>"
        for label, value in fields
    )
    link = tender.get("url") or ""
    link_html = (
        f"<p style='margin:10px 0 0'><a href='{_esc(link)}' "
        f"style='color:#00338D;font-weight:bold'>Open the notice &rarr;</a></p>"
        if link else ""
    )
    return f"""
    <div style="border:1px solid #DDD;border-left:5px solid {_score_colour(tender.get('score', 0))};
                padding:14px 18px;margin-bottom:16px">
      <h3 style="margin:0 0 4px;font-size:15px;color:#111">
        {tender.get('rank')}. {_esc(tender.get('title'))}
      </h3>
      <div style="margin-bottom:8px">{_flags_html(tender)}</div>
      <table style="border-collapse:collapse;font-size:13px">{rows}</table>
      <p style="font-size:13px;color:#333;margin:10px 0 0">
        <b>Description:</b> {_esc(description) or 'Not provided in the notice.'}
      </p>
      {link_html}
    </div>
    """


def _compact_table(tenders: list[dict]) -> str:
    header = (
        "<tr style='background:#00338D;color:#fff;text-align:left'>"
        "<th style='padding:6px'>#</th><th style='padding:6px'>Title</th>"
        "<th style='padding:6px'>Portal</th><th style='padding:6px'>Deadline</th>"
        "<th style='padding:6px'>Score</th></tr>"
    )
    rows = "".join(
        f"<tr style='background:{_score_colour(t.get('score', 0))}'>"
        f"<td style='padding:5px'>{t.get('rank')}</td>"
        f"<td style='padding:5px'><a href='{_esc(t.get('url'))}'>{_esc(t.get('title'))}</a></td>"
        f"<td style='padding:5px'>{_esc(t.get('portal'))}</td>"
        f"<td style='padding:5px'>{_esc(_fmt_date(t.get('closing_date'), 'n/a'))}</td>"
        f"<td style='padding:5px'>{t.get('score')}</td></tr>"
        for t in tenders
    )
    return (
        "<table style='border-collapse:collapse;width:100%;font-size:12px;"
        f"border:1px solid #CCC'>{header}{rows}</table>"
    )


def build_email_html(
    tenders: list[dict], statuses: list[dict], stats: dict, scan_time: datetime
) -> str:
    """Full HTML email body."""
    head = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;color:#222;max-width:900px">
      <h1 style="color:#00338D;font-size:20px;margin:0 0 4px">Jordan Tender Intelligence</h1>
      <p style="color:#666;font-size:13px;margin:0 0 18px">
        Automated donor and IFI procurement scan &middot; {scan_time.strftime('%d %B %Y')}
      </p>
      {_summary_html(statuses, stats, scan_time)}
    """

    if not tenders:
        failed = [s["name"] for s in statuses if not s["ok"]]
        note = (
            f"<p style='font-size:13px;color:#C00000'>Note: {len(failed)} portal(s) were "
            f"unavailable this run ({_esc(', '.join(failed))}), so coverage was incomplete. "
            "Please check those manually.</p>"
            if failed else ""
        )
        return head + f"""
      <div style="background:#FFF4CE;border-left:4px solid #8A6D00;padding:14px 18px">
        <h2 style="margin:0 0 6px;font-size:16px">No matching tenders this run</h2>
        <p style="font-size:13px;margin:0">The scan completed successfully but no
        tenders passed the current filters. Portal-by-portal results are listed above.</p>
      </div>
      {note}
    </div>"""

    inline = tenders[: config.MAX_INLINE_TENDERS]
    overflow = tenders[config.MAX_INLINE_TENDERS:]

    body = _top3_html(tenders)
    body += (
        f"<h2 style='font-size:16px;color:#00338D;margin:0 0 10px'>"
        f"All {len(tenders)} matching tenders &mdash; full detail</h2>"
    )
    body += "".join(_detail_block(t) for t in inline)

    if overflow:
        body += (
            f"<h2 style='font-size:16px;color:#00338D;margin:24px 0 8px'>"
            f"Remaining {len(overflow)} tenders (summary)</h2>"
            "<p style='font-size:12px;color:#666;margin:0 0 8px'>Full detail for these is "
            "in the attached workbook &mdash; the email is truncated here so Outlook does "
            "not clip it.</p>"
            + _compact_table(overflow)
        )

    footer = """
      <p style="font-size:11px;color:#888;margin-top:26px;border-top:1px solid #DDD;padding-top:10px">
        Generated automatically by the Jordan Tender Monitor. Scores are a relevance
        heuristic, not a bid/no-bid decision. Always verify deadlines, eligibility and
        scope against the original notice before acting.
      </p>
    </div>"""
    return head + body + footer


def build_subject(tenders: list[dict], scan_time: datetime) -> str:
    return config.EMAIL_SUBJECT_TEMPLATE.format(
        date=scan_time.strftime("%d %b %Y"), count=len(tenders)
    )


# --------------------------------------------------------------------------
# Output files
# --------------------------------------------------------------------------
def write_excel(tenders: list[dict], path: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Jordan Tenders"

    header_fill = PatternFill("solid", fgColor="00338D")
    header_font = Font(color="FFFFFF", bold=True)
    ws.append(EXCEL_COLUMNS)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(vertical="center")

    for tender in tenders:
        ws.append(_row_of(tender))
        row = ws.max_row
        fill = PatternFill("solid", fgColor=_score_rgb(tender.get("score", 0)))
        for col in range(1, len(EXCEL_COLUMNS) + 1):
            ws.cell(row=row, column=col).fill = fill
            ws.cell(row=row, column=col).alignment = Alignment(vertical="top", wrap_text=True)
        link_cell = ws.cell(row=row, column=EXCEL_COLUMNS.index("Link") + 1)
        if tender.get("url"):
            link_cell.hyperlink = tender["url"]
            link_cell.value = "Open notice"
            link_cell.font = Font(color="0563C1", underline="single")
        value_cell = ws.cell(row=row, column=EXCEL_COLUMNS.index("Value (USD)") + 1)
        if isinstance(value_cell.value, (int, float)):
            value_cell.number_format = '#,##0'

    widths = [6, 60, 20, 24, 22, 12, 12, 14, 8, 34, 30, 14]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(EXCEL_COLUMNS))}{max(ws.max_row, 1)}"

    wb.save(path)
    log.info("Excel written: %s", path)
    return path


def write_json(tenders: list[dict], statuses: list[dict], stats: dict, path: Path) -> Path:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stats": stats,
        "portals": statuses,
        "tenders": tenders,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    log.info("JSON written: %s", path)
    return path


def write_csv(tenders: list[dict], path: Path) -> Path:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(EXCEL_COLUMNS)
        for tender in tenders:
            writer.writerow(_row_of(tender))
    log.info("CSV written: %s", path)
    return path


def write_html(body_html: str, path: Path, subject: str) -> Path:
    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(subject)}</title></head>"
        f"<body style='margin:24px;background:#fff'>{body_html}</body></html>"
    )
    path.write_text(page, encoding="utf-8")
    log.info("HTML written: %s", path)
    return path


def build_outputs(
    tenders: list[dict], statuses: list[dict], stats: dict, scan_time: datetime
) -> dict:
    """Render the email body and write every configured output file."""
    body = build_email_html(tenders, statuses, stats, scan_time)
    subject = build_subject(tenders, scan_time)
    stamp = scan_time.strftime("%Y%m%d_%H%M")
    files: dict[str, Path] = {}

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    if "excel" in config.OUTPUT_FORMATS:
        files["excel"] = write_excel(tenders, config.OUTPUT_DIR / f"jordan_tenders_{stamp}.xlsx")
    if "json" in config.OUTPUT_FORMATS:
        files["json"] = write_json(
            tenders, statuses, stats, config.OUTPUT_DIR / f"jordan_tenders_{stamp}.json"
        )
    if "csv" in config.OUTPUT_FORMATS:
        files["csv"] = write_csv(tenders, config.OUTPUT_DIR / f"jordan_tenders_{stamp}.csv")
    if "html" in config.OUTPUT_FORMATS:
        files["html"] = write_html(body, config.OUTPUT_DIR / f"jordan_tenders_{stamp}.html", subject)

    return {"subject": subject, "body_html": body, "files": files}
