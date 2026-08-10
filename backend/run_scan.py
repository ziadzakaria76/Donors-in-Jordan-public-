"""Entry point for the scheduled scanner.

This is the command Replit's Scheduled Deployment runs. It is a separate
deployment from the web app on purpose: scheduled jobs and always-on web
services are different deployment types, and Replit terminates a scheduled
command when it finishes.

    python run_scan.py

Exit codes matter here, because Replit's failure alerting keys off them:
    0  the scan ran (including a scan that legitimately found nothing)
    1  every source failed, or the scan itself crashed
    0  the scan was skipped because another was still running — not a failure,
       and alerting on it would train us to ignore the alerts

Whatever happens, the outcome is also written to the database, so the app's
home screen can report it. Nobody should learn from silence that scanning
stopped a week ago.
"""

from __future__ import annotations

import logging
import sys

from app.adapters.registry import all_sources
from app.db import init_db, session_scope
from app.models import ScanStatus
from app.scan import run_scan
from app.scoring.engine import ScoringEngine
from app.scoring.profile import load_profile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("gulftrack.run_scan")


def main() -> int:
    init_db()
    engine = ScoringEngine(load_profile())
    adapters = all_sources()

    fetchable = [a for a in adapters if getattr(a, "access_mode", None) != "deep_link"]
    if not fetchable:
        log.warning(
            "No fetch sources are configured. Nothing to scan. This is "
            "recorded so the app can say so rather than showing a quiet zero."
        )

    with session_scope() as session:
        summary = run_scan(session, adapters, engine)

    log.info("Scan %s: %s", summary.scan_run_id, summary.describe())

    if summary.status is ScanStatus.FAILED:
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A crash must be loud. Replit alerts on a non-zero exit, and the
        # traceback belongs in the job log where a future repair can read it.
        log.exception("Scan crashed before it could record itself")
        sys.exit(1)
