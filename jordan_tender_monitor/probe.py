"""
Try a portal that has not been added yet, and report honestly what happened.

`--capture` answers "does this portal, which is in portals.json, still read?"
This answers the question that comes first: "would adding this URL work at
all?" -- without committing anything.

That distinction exists because of how the app adds a portal. The obvious
implementation is to commit the entry, run a diagnostic against it, and remove
it again if it was no good; that leaves a half-added portal in the repository,
two commits of noise per attempt, and a window where a scheduled run picks up
something nobody has looked at. So the candidate is sent to the workflow as
data, run through the same six-layer cascade every portal uses, and the result
comes back as a document the app can render.

WHAT THIS CAN AND CANNOT SETTLE. It reads the live page, so "the host blocked
us" and "the page loaded and carries no listing" are answered for certain. It
CANNOT tell you the rows are the right rows: GIZ's table once scored 1.00 with
every deadline garbage, because one unclosed cell nested the row inside the
deadline column. That is why the sample rows are in the output and why the
verdict says what was read rather than only how well it scored. A score is
evidence about shape, never about correctness.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import config, portal_config
from .portals import base, harvester
from .portals.htmlkit import QUALITY_THRESHOLD, diagnose

# Bumped when a field changes meaning or goes away. The app refuses a document
# from a newer pipeline rather than rendering fields it may misread.
PROBE_SCHEMA = 1

# Rows shown back. Enough to see whether the titles are notices or navigation,
# and whether the dates line up -- which three rows answers and one does not.
SAMPLE_ROWS = 3


def _row_to_dict(row) -> dict:
    return {
        "title": row.title,
        "url": row.url,
        "posted_text": row.date_text,
        "closing_text": row.closing_text,
        "value_text": row.value_text,
        "reference": row.reference,
        # What the date and value parsers actually see. When a row has a date
        # on screen and none in the record, the answer is almost always here
        # and nowhere else.
        "raw_text": (row.raw_text or "")[:400],
    }


def _verdict(sources: list[dict], portal: dict) -> dict:
    """One sentence on whether this portal is worth adding, and why.

    Deliberately not a score. "0.71" tells a reader nothing about what to do
    next; "read 24 rows, and here are three of them" does.
    """
    reachable = [s for s in sources if s["fetched"]]
    if not reachable:
        first = sources[0] if sources else {}
        return {
            "usable": False,
            "headline": "Nothing could be fetched",
            "detail": first.get("error") or "No source URL answered.",
            "advice": "Check the address in a browser. A bot wall or a "
                      "data-centre block reads the same from here as a wrong "
                      "URL, so the reason above is the best available.",
        }

    winners = [s for s in reachable if s["winner"]]
    if winners:
        best = max(winners, key=lambda s: s["winning_quality"])
        rows = best["winning_rows"]
        filtering = ("Jordan filtering is on, so the run will keep only the "
                     "rows that name Jordan."
                     if portal.get("filter_to_jordan", True) else
                     "Jordan filtering is off for this portal, so every row "
                     "will be reported.")
        return {
            "usable": True,
            "headline": f"Read {rows} row{'' if rows == 1 else 's'} "
                        f"from {best['url']}",
            "detail": f"The {best['winner']} layer won at quality "
                      f"{best['winning_quality']:.2f}. {filtering}",
            "advice": "Look at the sample rows before saving. A high score "
                      "means the page LOOKS like a listing; it cannot see a "
                      "column being wrong, and a wrong deadline column "
                      "silently drops open tenders.",
        }

    # Fetched, and nothing cleared the gate. The most common outcome for a URL
    # that is a landing page rather than a listing.
    best = max(reachable, key=lambda s: s["best_quality"])
    found = best["best_rows"]
    return {
        "usable": False,
        "headline": ("The page loaded and no layer found a listing"
                     if found == 0 else
                     f"Found {found} row(s), below the quality gate"),
        "detail": best.get("diagnosis") or "",
        "advice": ("Sample rows from the best-scoring layer are below even "
                   "though it was rejected -- whether they are notices "
                   "missing their dates or genuine rubbish is not something "
                   "the score can answer, only the rows can."),
    }


def probe(candidate: dict) -> dict:
    """Run one candidate portal through the cascade. Never raises."""
    problems: list[str] = []
    registry = portal_config.load_document({"portals": [candidate]},
                                           path="<probe>")
    if registry.problems:
        problems = [f"{p.key}: {p.message}" for p in registry.problems]

    portal = registry.portals[0] if registry.portals else None
    document: dict = {
        "schema": PROBE_SCHEMA,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "quality_threshold": QUALITY_THRESHOLD,
        "candidate": candidate,
        # The entry is validated with exactly the loader a run uses, so the
        # app cannot be told a portal is fine and then have the run reject it.
        "rejected": problems,
        "sources": [],
    }

    if portal is None:
        document["verdict"] = {
            "usable": False,
            "headline": "This portal would be rejected on load",
            "detail": "; ".join(problems),
            "advice": "Fix the entry and try again. Nothing was fetched.",
        }
        return document

    spec = harvester.HtmlSpec(
        key=portal.key,
        urls=list(portal.urls),
        selectors=list(portal.selectors),
        anchor_hint=portal.anchor_hint,
        currency=portal.currency,
        filter_to_jordan=portal.filter_to_jordan,
        field_selectors=dict(portal.field_selectors),
    )

    for url, html, layers in harvester.capture(spec):
        source: dict = {
            "url": url,
            "fetched": bool(html),
            "bytes": len(html or ""),
            "error": "",
            "layers": [],
            "winner": "",
            "winning_rows": 0,
            "winning_quality": 0.0,
            "best_rows": 0,
            "best_quality": 0.0,
            "diagnosis": "",
            "sample_rows": [],
            "sample_from": "",
            "sample_rejected": False,
        }

        if not html:
            source["error"] = layers[0].note if layers else "no content"
            document["sources"].append(source)
            continue

        winner = None
        for layer in layers:
            wins = (winner is None and bool(layer.rows)
                    and layer.quality >= QUALITY_THRESHOLD)
            if wins:
                winner = layer
            source["layers"].append({
                "layer": layer.layer,
                "rows": len(layer.rows),
                "quality": round(layer.quality, 3),
                "note": layer.note,
                "wins": wins,
            })

        scored = [layer for layer in layers if layer.rows]
        best = winner or max(scored, key=lambda layer: layer.quality,
                             default=None)
        if winner is not None:
            source["winner"] = winner.layer
            source["winning_rows"] = len(winner.rows)
            source["winning_quality"] = round(winner.quality, 3)
        else:
            # Say what is wrong with the page, in the same words the run
            # would use, rather than leaving the app to infer it from a zero.
            source["diagnosis"] = diagnose(html, [])

        if best is not None:
            source["best_rows"] = len(best.rows)
            source["best_quality"] = round(best.quality, 3)
            source["sample_from"] = best.layer
            source["sample_rejected"] = winner is None
            source["sample_rows"] = [_row_to_dict(r) for r in best.rows[:SAMPLE_ROWS]]

        document["sources"].append(source)

    document["verdict"] = _verdict(document["sources"], candidate)
    return document


def write_probe(candidate: dict, output_dir: Path | None = None) -> Path:
    """Run a probe and write it where the workflow will upload it."""
    output_dir = Path(output_dir or config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    key = str(candidate.get("key") or "candidate")
    # Sanitised: this becomes a filename, and the key came off a phone.
    safe = "".join(c for c in key if c.isalnum() or c in "-_") or "candidate"
    path = output_dir / f"probe_{safe}.json"

    try:
        document = probe(candidate)
    except base.PortalError as exc:
        # A diagnosed failure is a result, not a crash.
        document = {
            "schema": PROBE_SCHEMA,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "candidate": candidate,
            "sources": [],
            "verdict": {"usable": False, "headline": "The probe failed",
                        "detail": exc.reason, "advice": ""},
        }
    except Exception as exc:  # noqa: BLE001 - the app must always get a document
        document = {
            "schema": PROBE_SCHEMA,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "candidate": candidate,
            "sources": [],
            "verdict": {
                "usable": False,
                "headline": "The probe hit an unexpected error",
                "detail": f"{type(exc).__name__}: {exc}",
                "advice": "This is a bug in the monitor, not a fact about the "
                          "portal. The run log has the traceback.",
            },
        }

    path.write_text(json.dumps(document, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return path
