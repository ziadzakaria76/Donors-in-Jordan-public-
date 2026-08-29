"""Full structured export -- what makes a bad run diagnosable after the fact."""

from __future__ import annotations

import json
from pathlib import Path


def write_json(result, path: Path, profile: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run": {
            "started": result.started,
            "subject": result.subject(),
            "profile": profile.get("key"),
            "duplicates_collapsed": result.duplicates_collapsed,
            "expired_dropped": result.expired_dropped,
        },
        "portal_health": [
            {"portal": p.name, "label": p.label, "url": p.url, "available": p.available,
             "skipped_reason": p.skipped_reason, "error": p.error, "diagnosis": p.diagnosis,
             "fetched": p.stats.seen, "kept": len(p.tenders),
             "extraction_layer": p.layer, "extraction_quality": p.quality}
            for p in result.portals
        ],
        "classification_counts": result.counts,
        "screening": {"lists": result.screening_status, "error": result.screening_error},
        "tenders": [t.to_dict() for t in result.tenders],
        "excluded_from_scope": [t.to_dict() for t in result.excluded],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
