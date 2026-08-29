"""A short Markdown summary written beside the Word and Excel files.

This replaces what used to be the email body. Its real job is the one the
subject line used to do: make portal health visible without opening anything.
A scheduled run pipes it into the CI job summary, so a broken monitor is
apparent from the run list rather than only from a file nobody downloaded.
"""

from __future__ import annotations

from pathlib import Path

from ..models import LINK_TYPES
from .common import (LINK_LABELS, SCREENING_DISCLAIMER, badges, fmt_date, fmt_value,
                     split_live_pipeline)

MAX_ROWS = 60


def render_summary(result, top_n: int = 10) -> str:
    live, pipeline = split_live_pipeline(result.tenders)
    out: list[str] = [
        f"# {result.subject()}",
        "",
        f"Run {result.started} · {len(result.tenders)} in scope · "
        f"{len(result.new_tenders)} new · {len(result.excluded)} excluded but logged",
        "",
    ]

    out += [f"## Top {min(top_n, len(result.tenders))}", ""]
    if not result.tenders:
        out += ["_Nothing in scope this run. Check portal health below before "
                "concluding it was a quiet day._", ""]
    for rank, tender in enumerate(result.tenders[:top_n], start=1):
        title = f"[{tender.title}]({tender.url})" if tender.url else tender.title
        out.append(f"{rank}. **[{tender.score:.0f}]** {title}")
        out.append(f"   {tender.portal} · closes {fmt_date(tender.closing_date)} · "
                   f"{fmt_value(tender)}")
        marks = badges(tender)
        if marks:
            out.append(f"   `{' · '.join(marks)}`")
    out.append("")

    out += _table(f"Live — biddable ({len(live)})", live)
    out += _table(f"Pipeline — not yet biddable ({len(pipeline)})", pipeline)

    out += ["## Run diagnostics", ""]
    for portal in result.portals:
        mark = "✅" if portal.available and not portal.skipped_reason else (
            "⏭️" if portal.skipped_reason else "❌")
        out.append(f"- {mark} {portal.status_line}")
    out += ["", "**Classification split**", ""]
    for key in LINK_TYPES:
        out.append(f"- {LINK_LABELS.get(key, key)}: {result.counts.get(key, 0)}")
    out += ["", f"Duplicates collapsed: {result.duplicates_collapsed} · "
                f"expired dropped: {result.expired_dropped}", ""]

    if result.screening_error:
        out += [f"> **Screening error:** {result.screening_error}", ""]
    for entry in result.screening_status:
        out.append(f"- {entry['list']}: fetched {entry['fetched']}, {entry['names']} names")
    out += ["", f"_{SCREENING_DISCLAIMER}_", ""]
    return "\n".join(out)


def _table(heading: str, tenders: list) -> list[str]:
    if not tenders:
        return [f"## {heading}", "", "_none_", ""]
    rows = [f"## {heading}", "",
            "| | Title | Portal | Closes | Value |",
            "|---|---|---|---|---|"]
    for tender in tenders[:MAX_ROWS]:
        title = f"[{tender.title}]({tender.url})" if tender.url else tender.title
        rows.append(f"| {'NEW' if tender.is_new else ''} | {title} | {tender.portal} | "
                    f"{fmt_date(tender.closing_date)} | {fmt_value(tender)} |")
    if len(tenders) > MAX_ROWS:
        rows.append("")
        rows.append(f"_+{len(tenders) - MAX_ROWS} more — see the Word and Excel files._")
    rows.append("")
    return rows


def write_summary(result, path: Path, top_n: int = 10) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_summary(result, top_n), encoding="utf-8")
    return path
