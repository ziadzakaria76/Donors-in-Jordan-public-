"""A single static HTML page for the run.

Written to site/, which is NOT committed -- it is a local view, regenerated
every run. Self-contained: no CDN, no fonts, no scripts, so it opens from a
file:// URL on any machine.
"""

from __future__ import annotations

import datetime as _dt
import html
from pathlib import Path

STYLE = """
:root { --ink:#1a1a1a; --muted:#666; --line:#e3e3e3; --accent:#1f3864;
        --ok:#e2efda; --warn:#fff2cc; --bad:#fce4e4; --bg:#fff; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#e8e8e8; --muted:#a0a0a0; --line:#333; --accent:#8fb3e8;
          --ok:#22371f; --warn:#3a3320; --bad:#3d2222; --bg:#151515; }
}
* { box-sizing:border-box; }
body { margin:0; padding:2rem 1.25rem; background:var(--bg); color:var(--ink);
       font:14px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
main { max-width:1100px; margin:0 auto; }
h1 { font-size:1.6rem; margin:0 0 .25rem; }
.sub { color:var(--muted); margin:0 0 1.75rem; }
h2 { font-size:1.1rem; margin:2.25rem 0 .75rem; padding-bottom:.35rem;
     border-bottom:2px solid var(--accent); }
.wrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:13px; }
th { text-align:left; background:var(--accent); color:#fff; padding:.5rem .6rem;
     position:sticky; top:0; white-space:nowrap; }
td { padding:.45rem .6rem; border-bottom:1px solid var(--line); vertical-align:top; }
tr.short td { background:var(--ok); }
.s-ok{background:var(--ok);} .s-empty{background:var(--warn);}
.s-error,.s-blocked{background:var(--bad);} .s-skipped{background:var(--line);}
.badge { display:inline-block; padding:.1rem .45rem; border-radius:3px; font-size:12px; }
.notice { background:var(--bad); border-left:4px solid #c0392b; padding:.85rem 1rem;
          margin:1rem 0; border-radius:3px; }
a { color:var(--accent); }
"""


def _row(cells: list[str], klass: str = "") -> str:
    attr = f' class="{klass}"' if klass else ""
    return f"<tr{attr}>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def write_html(path, postings, run_log, config) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    esc = html.escape
    totals = run_log.totals()

    notice = ""
    if totals["ok"] == 0:
        notice = (
            '<div class="notice"><strong>No source returned any postings.</strong> '
            "An empty table below means the scan could not read any employer — not "
            "that there are no vacancies. The run status table gives the reason for "
            "each source.</div>"
        )

    posting_rows = "".join(
        _row(
            [
                esc(p.source_key),
                f'<a href="{esc(p.url)}">{esc(p.title)}</a>' if p.url else esc(p.title),
                esc(p.location),
                esc(p.posted_at.isoformat() if p.posted_at else "—"),
                str(p.score),
                esc(", ".join(p.matched_terms)),
            ],
            "short" if p.shortlisted else "",
        )
        for p in sorted(postings, key=lambda x: (-x.score, x.source_key))
    ) or _row(["—"] * 6)

    status_rows = "".join(
        _row(
            [
                esc(r.source_key),
                esc(r.platform),
                f'<span class="badge s-{esc(r.status)}">{esc(r.status)}</span>',
                str(r.fetched),
                str(r.kept),
                esc(r.error or "—"),
                esc(" | ".join(r.notes) or "—"),
            ]
        )
        for r in run_log.records
    ) or _row(["—"] * 7)

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job scan — {esc(config.profile.get('target', ''))}</title>
<style>{STYLE}</style></head><body><main>
<h1>Job scan — {esc(config.profile.get('target', ''))}</h1>
<p class="sub">{_dt.datetime.now(_dt.timezone.utc).isoformat(timespec='seconds')} ·
{totals['sources']} source(s) attempted · {totals['ok']} returned data ·
{len(postings)} posting(s) scored ·
{sum(1 for p in postings if p.shortlisted)} shortlisted</p>
{notice}
<h2>Postings</h2>
<div class="wrap"><table>
<thead><tr><th>Source</th><th>Title</th><th>Location</th><th>Posted</th>
<th>Score</th><th>Matched</th></tr></thead><tbody>{posting_rows}</tbody></table></div>
<h2>Run status</h2>
<div class="wrap"><table>
<thead><tr><th>Source</th><th>Platform</th><th>Status</th><th>Fetched</th>
<th>Kept</th><th>Error</th><th>Notes</th></tr></thead><tbody>{status_rows}</tbody></table></div>
</main></body></html>"""
    target.write_text(document, encoding="utf-8")
    return target
