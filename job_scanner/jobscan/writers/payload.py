"""Machine-readable dump of the run, for diffing one week against the next."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path


def write_json(path, postings, run_log, config) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "profile": {
            "target": config.profile.get("target", ""),
            "fingerprint": config.fingerprint(),
            "max_age_days": config.max_age_days,
            "shortlist_min_score": config.shortlist_min_score,
        },
        "totals": run_log.totals(),
        "run_status": [record.as_row() for record in run_log.records],
        "postings": [posting.as_row() for posting in postings],
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target
