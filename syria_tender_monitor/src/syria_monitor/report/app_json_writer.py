"""The report in the shape the Android app reads.

NOT A SECOND EXPORT OF THE SAME THING. json_writer.py writes this project's own
structured dump -- everything a run knew, for diagnosing it afterwards. This
writes a DIFFERENT document with a different contract: the one
jordan_tender_monitor/agents/reporter.py emits and the app parses.

WHY THE APP CANNOT SIMPLY READ THE OTHER FILE. The two documents disagree at
every level. Ours has no `schema`, so the app parses it as 0 and refuses to
render -- deliberately, since a screen of half-parsed fields that silently mean
something else is worse than a sentence saying the app is out of date. Ours
calls the portal list `portal_health`, the app wants `portals`; ours describes a
run with `started` and `subject`, the app wants `status`, `status_line` and
seven counts. Renaming a few keys would not close that.

WHY HERE AND NOT IN THE APP. The app is the expensive side to change: a new
contract means a new build, and every phone has to install it. This file is
regenerated on every run, so the bridge lives where it is cheap to move.

THE CONTRACT IS COPIED, NOT INVENTED. Field names, the schema constant and the
null-vs-zero rules below all come from Jordan's writer, which is the authority
because it is what the app was written against. Where this project has no
equivalent of one of its concepts -- tiers, most obviously -- the app's own
default is emitted and said to be a placeholder rather than a claim.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .common import fmt_value

# The app refuses a schema it was not written for. This is Jordan's constant and
# must move only when the app does: it is a statement about what the OLD fields
# mean, not a version number for this file.
REPORT_SCHEMA = 1

# This project does not rank its sources, so there is no tier to report. The
# app's own default is sent rather than a number invented here, and the label is
# left empty so nothing renders a tier that was never assigned.
_PLACEHOLDER_TIER = 2


def _status(portal) -> str:
    """One machine-readable word, using the app's own vocabulary.

    "unconfigured" rather than a new word for a skipped portal: SAM.gov without
    its key is exactly what Jordan means by unconfigured, and inventing a fifth
    status would be a field the app cannot render.
    """
    if portal.skipped_reason:
        return "unconfigured"
    if not portal.available:
        return "unavailable"
    return "ok"


def _reason(portal) -> str:
    return portal.skipped_reason or portal.error or portal.diagnosis or ""


def _scanned(portal):
    """Notices read before filtering, or None when the portal never filtered.

    NULL IS NOT ZERO and the difference is the whole point of the field: "read
    nothing" and "read five hundred and none were relevant" are the two
    diagnoses it exists to separate, and rendering the second as 0 destroys it.
    A portal that was skipped or unavailable never reached its filter, so it
    reports null rather than the 0 its stats happen to hold.
    """
    if portal.skipped_reason or not portal.available:
        return None
    return portal.stats.seen


def _days_left(closing, today: date):
    return (closing - today).days if closing else None


def run_status(reported: int, portals: list) -> str:
    """The run's outcome as one word, on Jordan's four-case definition.

    Re-derived here rather than imported, because the two projects share no
    code -- but deliberately to the same rule, since an app that saw one
    definition from one country and another from the other would disagree with
    itself and the disagreement would be invisible.
    """
    considered = [p for p in portals if not p.skipped_reason]
    broken = [p for p in considered if not p.available]
    if considered and len(broken) == len(considered):
        return "action_needed"
    if broken:
        return "partial"
    if reported == 0:
        return "quiet"
    return "ok"


def write_app_json(result, path: Path, profile: dict, today: date | None = None,
                   new_only: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    today = today or date.today()

    labels = {p.name: p.label for p in result.portals}
    considered = [p for p in result.portals if not p.skipped_reason]
    broken = [p for p in considered if not p.available]
    scanned = sum(p.stats.seen for p in result.portals)

    def tender(t) -> dict:
        return {
            "id": t.id,
            "title": t.title,
            "portal": t.portal,
            "portal_name": labels.get(t.portal, t.portal),
            "url": t.url,
            "score": round(t.score, 1),
            "sector": t.sector,
            "notice_type": t.notice_type,
            "language": t.language,
            "flags": list(t.flags),
            "posted_date": t.posted_date.isoformat() if t.posted_date else None,
            "closing_date": t.closing_date.isoformat() if t.closing_date else None,
            "days_left": _days_left(t.closing_date, today),
            "estimated_value_usd": t.estimated_value_usd,
            "value_display": fmt_value(t),
            "eligibility": t.eligibility,
            "contact": t.contact,
            "description": t.description,
            # Beyond the app's contract, and harmless: it parses with
            # ignoreUnknownKeys, so an older build ignores these while a later
            # one can show which country a row belongs to without a new schema.
            "country": profile.get("name", ""),
            "delivery_country": t.delivery_country,
        }

    payload = {
        "schema": REPORT_SCHEMA,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run": {
            "status": run_status(len(result.tenders), result.portals),
            "status_line": result.subject(),
            "slug": f"{len(result.tenders)}-opportunities",
            "opportunity_count": len(result.tenders),
            "scanned": scanned,
            "merged_duplicates": result.duplicates_collapsed,
            "dropped": {"expired": result.expired_dropped},
            "portals_total": len(considered),
            "portals_ok": len(considered) - len(broken),
            "portals_broken": len(broken),
            "new_only": new_only,
        },
        "tender_count": len(result.tenders),
        "tenders": [tender(t) for t in result.tenders],
        "portals": [
            {"key": p.name, "name": p.label, "tier": _PLACEHOLDER_TIER,
             "tier_label": "", "status": _status(p), "count": len(p.tenders),
             "scanned": _scanned(p), "reason": _reason(p),
             "urls": [p.url] if p.url else [],
             "layer": p.layer or "", "quality": p.quality or 0.0}
            for p in result.portals
        ],
    }
    # ensure_ascii=False so Arabic survives as Arabic rather than \uXXXX.
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
