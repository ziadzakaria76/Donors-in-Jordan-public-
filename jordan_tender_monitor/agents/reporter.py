"""
Reporter agent: the email body, the subject line, and five output files.

Two things here are load-bearing.

THE SUBJECT LINE CARRIES PORTAL HEALTH (Q15). If the subject says
"0 opportunities" whether every portal failed or every portal worked and
nothing matched, a dead monitor goes unnoticed for weeks and you find out when
someone asks why you missed a bid. So:

    Jordan Tenders - 7 new opportunities
    Jordan Tenders - no new opportunities (13/13 portals OK)
    Jordan Tenders - 4 new, 3 portals unavailable
    ACTION NEEDED: Jordan Tenders - all 13 portals unreachable

THE EMAIL NEVER DROPS A TENDER. Outlook clips messages over roughly 100 KB and
hides the tail without saying so, so full detail is rendered for the top
MAX_INLINE_TENDERS by score and the remainder MOVES to a compact table with a
pointer to the attachments. Moving is not dropping.
"""

from __future__ import annotations

import csv
import html
import json
import logging
from datetime import date, datetime
from pathlib import Path

from .. import config
from ..utils import money
from ..utils.dates import days_until, fmt
from ..utils.text import truncate

log = logging.getLogger(__name__)

COLUMNS = [
    ("score", "Score"),
    ("title", "Title"),
    ("portal_name", "Portal"),
    ("notice_type", "Notice type"),
    ("sector", "Sector"),
    ("posted_date", "Published"),
    ("closing_date", "Deadline"),
    ("days_left", "Days left"),
    ("value_display", "Estimated value"),
    ("language", "Language"),
    ("flags_display", "Flags"),
    ("eligibility", "Eligibility"),
    ("contact", "Contact"),
    ("url", "Link"),
]


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------


def decorate(tenders: list[dict], today: date | None = None) -> list[dict]:
    """Add display-only fields. Never mutates the underlying data meaning."""
    today = today or date.today()
    for t in tenders:
        t["portal_name"] = config.PORTAL_NAMES.get(t.get("portal"), t.get("portal"))
        t["value_display"] = money.format_usd(t.get("estimated_value_usd"))
        left = days_until(t.get("closing_date"), today)
        t["days_left"] = "" if left is None else left
        t["flags_display"] = "; ".join(t.get("flags") or [])
        t["posted_display"] = fmt(t.get("posted_date"))
        t["closing_display"] = fmt(t.get("closing_date"))
    return tenders


def build_subject(reported: int, health: list, first_run: bool = False) -> str:
    """Subject line that states the run's health, not just its count."""
    broken = [h for h in health if getattr(h, "broken", False)]
    total = len([h for h in health if getattr(h, "status", "") != "unconfigured"])
    ok = total - len(broken)
    prefix = config.EMAIL_SUBJECT_PREFIX

    if total and len(broken) == total:
        return f"{config.ACTION_NEEDED_PREFIX}: {prefix} - all {total} portals unreachable"

    first = " (first run - full pipeline)" if first_run and reported else ""

    if broken:
        noun = "opportunity" if reported == 1 else "opportunities"
        return (f"{prefix} - {reported} new {noun}, "
                f"{len(broken)} of {total} portals unavailable{first}")

    if reported == 0:
        return f"{prefix} - no new opportunities ({ok}/{total} portals OK)"

    noun = "opportunity" if reported == 1 else "opportunities"
    return f"{prefix} - {reported} new {noun}{first}"


# ---------------------------------------------------------------------------
# HTML email body
# ---------------------------------------------------------------------------

_CSS = """
body{font-family:Segoe UI,Helvetica,Arial,sans-serif;font-size:14px;color:#222;line-height:1.45}
h1{font-size:19px;margin:0 0 4px}h2{font-size:16px;margin:22px 0 8px;
   border-bottom:2px solid #1F4E79;padding-bottom:3px;color:#1F4E79}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px}
th{background:#1F4E79;color:#fff;text-align:left;padding:6px;font-weight:600}
td{border-bottom:1px solid #ddd;padding:6px;vertical-align:top}
.t{border:1px solid #ddd;border-left:5px solid #1F4E79;padding:10px 12px;margin:10px 0;
   border-radius:3px;background:#fafafa}
.t h3{margin:0 0 6px;font-size:15px}
.hi{border-left-color:#2E7D32}.mid{border-left-color:#F9A825}.lo{border-left-color:#C62828}
.meta{font-size:12px;color:#555;margin:2px 0}
.flag{display:inline-block;background:#FFF3CD;border:1px solid #FFE08A;color:#7A5B00;
      padding:1px 6px;border-radius:9px;font-size:11px;margin:2px 3px 2px 0}
.err{background:#FDECEA;border:1px solid #F5C2C0;padding:10px;border-radius:3px}
.rtl{direction:rtl;text-align:right}
.small{font-size:12px;color:#666}
"""


def _band(score: float) -> str:
    return "hi" if score >= 70 else ("mid" if score >= 40 else "lo")


def _e(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _tender_block(t: dict) -> str:
    rtl = ' class="rtl"' if t.get("language") == "ar" else ""
    flags = "".join(f'<span class="flag">{_e(f)}</span>' for f in (t.get("flags") or []))
    also = ""
    if t.get("also_on"):
        also = f'<div class="meta">Also published on: {_e(", ".join(t["also_on"]))}</div>'
    link = (f'<div class="meta"><a href="{_e(t.get("url"))}">Open the notice</a></div>'
            if t.get("url") else '<div class="meta">No direct link published</div>')
    desc = truncate(t.get("description") or "", config.DESCRIPTION_CHAR_LIMIT)
    contact = (f'<div class="meta"><b>Contact:</b> {_e(t["contact"])}</div>'
               if t.get("contact") else "")
    days = t.get("days_left")
    days_txt = f" ({days} days left)" if days != "" and days is not None else ""

    return f"""
<div class="t {_band(t.get('score', 0))}"{rtl}>
  <h3>{_e(t.get('title'))}</h3>
  <div class="meta"><b>Score {t.get('score')}</b> &middot; {_e(t.get('portal_name'))}
      &middot; {_e(t.get('sector'))} &middot; {_e(t.get('notice_type') or 'Type unspecified')}</div>
  <div class="meta"><b>Published:</b> {_e(t.get('posted_display'))}
      &nbsp;|&nbsp; <b>Deadline:</b> {_e(t.get('closing_display'))}{_e(days_txt)}
      &nbsp;|&nbsp; <b>Value:</b> {_e(t.get('value_display'))}</div>
  {contact}{also}
  <div class="meta">{_e(desc)}</div>
  {flags}
  {link}
</div>"""


def _health_table(health: list) -> str:
    rows = []
    for h in health:
        if h.status == "ok":
            status = '<span style="color:#2E7D32">OK</span>'
            detail = f"{h.count} Jordan notice(s)"
            if h.layer:
                detail += f" &middot; via {_e(h.layer)} layer (quality {h.quality:.2f})"
        elif h.status == "unconfigured":
            status = '<span style="color:#8A6D00">NOT CONFIGURED</span>'
            detail = _e(h.reason)
        else:
            status = '<span style="color:#C62828"><b>UNAVAILABLE</b></span>'
            urls = "<br>".join(f'<a href="{_e(u)}">{_e(u)}</a>' for u in h.urls[:2])
            detail = f"{_e(h.reason)}<br><span class='small'>Check by hand: {urls}</span>"
        tier = config.TIER_LABELS.get(h.tier, "")
        rows.append(f"<tr><td>{_e(h.name)}<br><span class='small'>{_e(tier)}</span></td>"
                    f"<td>{status}</td><td>{detail}</td></tr>")
    return ("<table><tr><th>Portal</th><th>Status</th><th>Detail</th></tr>"
            + "".join(rows) + "</table>")


def _overflow_table(tenders: list[dict]) -> str:
    rows = []
    for t in tenders:
        title = (f'<a href="{_e(t.get("url"))}">{_e(t.get("title"))}</a>'
                 if t.get("url") else _e(t.get("title")))
        rows.append(
            f"<tr><td>{_e(t.get('score'))}</td><td>{title}</td>"
            f"<td>{_e(t.get('portal_name'))}</td><td>{_e(t.get('closing_display'))}</td>"
            f"<td>{_e(t.get('value_display'))}</td></tr>")
    return ("<table><tr><th>Score</th><th>Title</th><th>Portal</th>"
            "<th>Deadline</th><th>Value</th></tr>" + "".join(rows) + "</table>")


def build_email_html(result: dict, health: list, first_run: bool = False) -> str:
    tenders = result["tenders"]
    today = date.today()
    broken = [h for h in health if getattr(h, "broken", False)]
    total = len([h for h in health if h.status != "unconfigured"])

    banner = ""
    if broken and len(broken) == total:
        banner = (f'<div class="err"><b>ACTION NEEDED.</b> All {total} portals were '
                  f'unreachable this run. This report is empty because nothing could '
                  f'be read, not because nothing was published. See the portal status '
                  f'table below.</div>')
    elif broken:
        names = ", ".join(h.name for h in broken)
        banner = (f'<div class="err"><b>{len(broken)} of {total} portals unavailable:</b> '
                  f'{_e(names)}. The opportunities below are therefore a partial '
                  f'picture. Details in the portal status table.</div>')

    first_note = ""
    if first_run and tenders:
        first_note = ('<p class="small">This is the first run, so the seen-tenders '
                      'database was empty and the whole open pipeline is reported. '
                      'From the next run onward only new notices appear.</p>')

    inline = tenders[:config.MAX_INLINE_TENDERS]
    overflow = tenders[config.MAX_INLINE_TENDERS:]

    parts = [
        f"<html><head><meta charset='utf-8'><style>{_CSS}</style></head><body>",
        "<h1>Jordan Tender Intelligence</h1>",
        f"<div class='small'>{today.strftime('%A %d %B %Y')} &middot; "
        f"{len(tenders)} opportunit{'y' if len(tenders)==1 else 'ies'} reported "
        f"&middot; {result['scanned']} notices scanned across {total} portals</div>",
        banner, first_note,
    ]

    if tenders:
        parts.append(f"<h2>Opportunities ({len(inline)} shown in full)</h2>")
        parts.extend(_tender_block(t) for t in inline)
        if overflow:
            parts.append(
                f"<h2>Further opportunities ({len(overflow)})</h2>"
                f"<p class='small'>Listed compactly to keep this email under Outlook's "
                f"clipping limit. Nothing has been dropped &mdash; full detail for every "
                f"one of these is in the attached Word and Excel files.</p>")
            parts.append(_overflow_table(overflow))
    else:
        if not broken:
            parts.append("<h2>No new opportunities</h2><p>Every portal was read "
                         "successfully and nothing new matched. This is a genuine "
                         "quiet run, not a failure &mdash; see the status table.</p>")

    dropped = result.get("dropped") or {}
    if dropped:
        items = ", ".join(f"{v} {k}" for k, v in sorted(dropped.items()))
        parts.append(f"<p class='small'><b>Filtered out this run:</b> {_e(items)}. "
                     f"Merged as duplicates across portals: "
                     f"{result.get('merged_duplicates', 0)}.</p>")

    parts.append("<h2>Portal status</h2>")
    parts.append(_health_table(health))

    weights = ", ".join(f"{k} {v:.1f}" for k, v in result.get("weights", {}).items())
    parts.append(f"<p class='small'>Scoring weights in force (renormalised to 100 "
                 f"after dropping components with a disabled filter): {_e(weights)}.</p>")
    parts.append("</body></html>")
    return "\n".join(p for p in parts if p)


def build_text_body(result: dict, health: list) -> str:
    """Plain-text alternative, for clients that will not render HTML."""
    lines = [f"Jordan Tender Intelligence - {date.today().isoformat()}", ""]
    for t in result["tenders"]:
        lines += [
            f"[{t.get('score')}] {t.get('title')}",
            f"    {t.get('portal_name')} | {t.get('sector')} | "
            f"deadline {t.get('closing_display')} | {t.get('value_display')}",
        ]
        if t.get("flags"):
            lines.append(f"    flags: {'; '.join(t['flags'])}")
        if t.get("url"):
            lines.append(f"    {t['url']}")
        lines.append("")
    lines.append("Portal status:")
    for h in health:
        lines.append(f"  {h.name}: {h.status.upper()}"
                     + (f" ({h.count})" if h.ok else f" - {h.reason}"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output files
# ---------------------------------------------------------------------------


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def _cell(t: dict, key: str):
    value = t.get(key)
    if isinstance(value, date):
        return value.isoformat()
    return "" if value is None else value


def write_excel(tenders: list[dict], path: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Jordan tenders"

    headers = [label for _, label in COLUMNS]
    ws.append(headers)

    # openpyxl requires BARE hex. "#1F4E79" raises; "1F4E79" is correct.
    header_fill = PatternFill(start_color=config.COLOR_HEADER,
                              end_color=config.COLOR_HEADER, fill_type="solid")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    for t in tenders:
        ws.append([_cell(t, key) for key, _ in COLUMNS])
        fill_hex = (config.COLOR_HIGH if (t.get("score") or 0) >= 70
                    else config.COLOR_MEDIUM if (t.get("score") or 0) >= 40
                    else config.COLOR_LOW)
        fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")
        for cell in ws[ws.max_row]:
            cell.fill = fill
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    widths = [8, 60, 24, 16, 22, 12, 12, 10, 18, 10, 34, 34, 28, 46]
    for i, width in enumerate(widths[:len(COLUMNS)], start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"

    # Setting auto_filter over a header-only range is a classic crash, and it
    # happens on precisely the quiet day when nothing matched.
    if tenders:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{ws.max_row}"

    wb.save(path)
    return path


def write_docx(tenders: list[dict], health: list, result: dict, path: Path) -> Path:
    """Word bid-review pack -- the artefact that circulates and takes comments."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    doc = Document()
    doc.add_heading("Jordan Tender Intelligence", level=0)
    subtitle = doc.add_paragraph(date.today().strftime("%A %d %B %Y"))
    subtitle.runs[0].font.size = Pt(11)
    doc.add_paragraph(
        f"{len(tenders)} opportunities reported from {result.get('scanned', 0)} "
        f"notices scanned. Ranked by fit score."
    )

    broken = [h for h in health if getattr(h, "broken", False)]
    if broken:
        warn = doc.add_paragraph()
        run = warn.add_run(
            f"{len(broken)} portal(s) were unavailable this run, so this is a "
            f"partial picture: " + ", ".join(h.name for h in broken))
        run.bold = True
        run.font.color.rgb = RGBColor(0xC6, 0x28, 0x28)

    for t in tenders:
        doc.add_heading(t.get("title") or "(untitled)", level=2)
        meta = doc.add_paragraph()
        meta.add_run(f"Score {t.get('score')}").bold = True
        meta.add_run(f"  |  {t.get('portal_name')}  |  {t.get('sector')}"
                     f"  |  {t.get('notice_type') or 'Type unspecified'}")
        doc.add_paragraph(
            f"Published: {t.get('posted_display')}    "
            f"Deadline: {t.get('closing_display')}    "
            f"Estimated value: {t.get('value_display')}")
        if t.get("flags"):
            flagline = doc.add_paragraph()
            flagline.add_run("Flags: " + "; ".join(t["flags"])).italic = True
        if t.get("contact"):
            doc.add_paragraph(f"Contact: {t['contact']}")
        if t.get("also_on"):
            doc.add_paragraph(f"Also published on: {', '.join(t['also_on'])}")
        if t.get("description"):
            body = doc.add_paragraph(truncate(t["description"], 2000))
            if t.get("language") == "ar":
                body.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if t.get("url"):
            doc.add_paragraph(t["url"])

    doc.add_page_break()
    doc.add_heading("Portal status", level=1)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text = "Portal", "Status", "Detail"
    for h in health:
        cells = table.add_row().cells
        cells[0].text = h.name
        cells[1].text = h.status.upper()
        cells[2].text = (f"{h.count} notice(s)" if h.ok
                         else f"{h.reason}  ({'; '.join(h.urls[:1])})")

    doc.save(path)
    return path


def write_json(tenders: list[dict], health: list, path: Path) -> Path:
    def encode(obj):
        if isinstance(obj, date):
            return obj.isoformat()
        raise TypeError(type(obj))

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tender_count": len(tenders),
        "tenders": [
            {k: v for k, v in t.items() if not k.startswith("_")}
            for t in tenders
        ],
        "portals": [
            {"key": h.key, "name": h.name, "tier": h.tier, "status": h.status,
             "count": h.count, "reason": h.reason, "urls": h.urls}
            for h in health
        ],
    }
    # ensure_ascii=False so Arabic survives as Arabic rather than \uXXXX.
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=encode),
                    encoding="utf-8")
    return path


def write_csv(tenders: list[dict], path: Path) -> Path:
    # utf-8-sig: without the BOM, Excel opens Arabic as mojibake.
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow([label for _, label in COLUMNS])
        for t in tenders:
            writer.writerow([_cell(t, key) for key, _ in COLUMNS])
    return path


def write_html(body_html: str, path: Path) -> Path:
    path.write_text(body_html, encoding="utf-8")
    return path


def write_outputs(result: dict, health: list, body_html: str,
                  output_dir: Path | None = None) -> dict[str, Path]:
    """Write every configured output format. Returns format -> path."""
    output_dir = Path(output_dir or config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    tenders = result["tenders"]
    stamp = _stamp()
    written: dict[str, Path] = {}

    for fmt_name in config.OUTPUT_FORMATS:
        try:
            if fmt_name == "excel":
                written["excel"] = write_excel(tenders, output_dir / f"jordan_tenders_{stamp}.xlsx")
            elif fmt_name == "docx":
                written["docx"] = write_docx(tenders, health, result,
                                             output_dir / f"jordan_tenders_{stamp}.docx")
            elif fmt_name == "json":
                written["json"] = write_json(tenders, health, output_dir / f"jordan_tenders_{stamp}.json")
            elif fmt_name == "csv":
                written["csv"] = write_csv(tenders, output_dir / f"jordan_tenders_{stamp}.csv")
            elif fmt_name == "html":
                written["html"] = write_html(body_html, output_dir / f"jordan_tenders_{stamp}.html")
        except Exception as exc:  # noqa: BLE001 - one format must not lose the rest
            log.error("could not write %s output: %s", fmt_name, exc)

    return written


def attachments_for_email(written: dict[str, Path]) -> list[Path]:
    return [written[f] for f in config.EMAIL_ATTACH_FORMATS if f in written]
