"""HTML email body -- same layering as the Word pack, compressed."""

from __future__ import annotations

from html import escape

from ..models import LINK_TYPES
from .common import (LINK_LABELS, SCREENING_DISCLAIMER, badges, fmt_date, fmt_value,
                     split_live_pipeline)

MAX_ROWS_IN_EMAIL = 60


def render_email(result, top_n: int = 10) -> str:
    live, pipeline = split_live_pipeline(result.tenders)
    parts = [
        "<div style=\"font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1f2328\">",
        f"<h2 style=\"margin:0 0 4px\">{escape(result.subject())}</h2>",
        f"<p style=\"color:#6b7280;margin:0 0 16px\">Run {escape(result.started)} &middot; "
        f"{len(result.tenders)} in scope &middot; {len(result.new_tenders)} new &middot; "
        f"{len(result.excluded)} excluded but logged</p>",
    ]

    parts.append(f"<h3>Top {min(top_n, len(result.tenders))}</h3><ol>")
    for tender in result.tenders[:top_n]:
        marks = " ".join(f"<span style=\"background:#fff3cd;padding:1px 4px;border-radius:3px\">"
                         f"{escape(b)}</span>" for b in badges(tender))
        link = f"<a href=\"{escape(tender.url)}\">{escape(tender.title)}</a>" if tender.url \
            else escape(tender.title)
        parts.append(
            f"<li style=\"margin-bottom:6px\"><b>[{tender.score:.0f}]</b> {link}<br>"
            f"<span style=\"color:#6b7280\">{escape(tender.portal)} &middot; closes "
            f"{escape(fmt_date(tender.closing_date))} &middot; {escape(fmt_value(tender))}</span> "
            f"{marks}</li>")
    parts.append("</ol>")

    parts.append(_table(f"Live &mdash; biddable ({len(live)})", live))
    parts.append(_table(f"Pipeline &mdash; not yet biddable ({len(pipeline)})", pipeline))

    parts.append("<h3>Run diagnostics</h3><ul>")
    for portal in result.portals:
        colour = "#b02a2a" if not portal.available else "#6b7280"
        parts.append(f"<li style=\"color:{colour}\">{escape(portal.status_line)}</li>")
    parts.append("</ul><p><b>Classification split</b><br>")
    parts.append(" &middot; ".join(f"{LINK_LABELS.get(k, k)}: {result.counts.get(k, 0)}"
                                   for k in LINK_TYPES))
    parts.append("</p>")

    if result.screening_error:
        parts.append(f"<p style=\"color:#b02a2a\"><b>Screening error:</b> "
                     f"{escape(result.screening_error)}</p>")
    for entry in result.screening_status:
        parts.append(f"<p style=\"color:#6b7280;margin:2px 0\">{escape(entry['list'])}: fetched "
                     f"{escape(str(entry['fetched']))}, {entry['names']} names</p>")
    parts.append(f"<p style=\"color:#b02a2a\"><b>{escape(SCREENING_DISCLAIMER)}</b></p></div>")
    return "".join(parts)


def _table(heading: str, tenders: list) -> str:
    if not tenders:
        return f"<h3>{heading}</h3><p style=\"color:#6b7280\">none</p>"
    rows = []
    for tender in tenders[:MAX_ROWS_IN_EMAIL]:
        title = escape(tender.title)
        direction = ' dir="rtl"' if tender.language == "ar" else ""
        link = f"<a href=\"{escape(tender.url)}\">{title}</a>" if tender.url else title
        rows.append(
            f"<tr><td style=\"padding:3px 6px\">{'NEW' if tender.is_new else ''}</td>"
            f"<td style=\"padding:3px 6px\"{direction}>{link}</td>"
            f"<td style=\"padding:3px 6px\">{escape(tender.portal)}</td>"
            f"<td style=\"padding:3px 6px\">{escape(fmt_date(tender.closing_date))}</td>"
            f"<td style=\"padding:3px 6px\">{escape(fmt_value(tender))}</td></tr>")
    overflow = ""
    if len(tenders) > MAX_ROWS_IN_EMAIL:
        overflow = (f"<p style=\"color:#6b7280\">+{len(tenders) - MAX_ROWS_IN_EMAIL} more &mdash; "
                    f"see the attached Word and Excel files.</p>")
    return (f"<h3>{heading}</h3><table style=\"border-collapse:collapse;font-size:13px\">"
            f"<tr style=\"background:#1b4f72;color:#fff\"><th></th><th>Title</th><th>Portal</th>"
            f"<th>Closes</th><th>Value</th></tr>{''.join(rows)}</table>{overflow}")
