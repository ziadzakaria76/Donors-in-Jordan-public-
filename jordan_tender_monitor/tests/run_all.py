#!/usr/bin/env python3
"""
Run the whole offline suite. No network, no credentials.

    python tests/run_all.py

State is redirected to a temporary directory BEFORE config is imported, so no
test can touch the real seen-tenders database or the real output folder.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT.parent))

# Must happen before `config` is imported anywhere: it reads these at import
# time. A suite that wrote fixture IDs into the real database would make the
# next live run report nothing and look broken.
_TMP = tempfile.mkdtemp(prefix="jtm-tests-")
os.environ.setdefault("JTM_DATA_DIR", str(Path(_TMP) / "data"))
os.environ.setdefault("JTM_OUTPUT_DIR", str(Path(_TMP) / "output"))
os.environ.setdefault("JTM_SEEN_DB", str(Path(_TMP) / "data" / "seen_tenders.db"))
os.environ.setdefault("JTM_LOG_FILE", str(Path(_TMP) / "test.log"))

# Silence the application logger. Tests deliberately provoke failures that the
# code logs with tracebacks, and that noise would bury a genuine test failure.
logging.disable(logging.CRITICAL)

from jordan_tender_monitor import config  # noqa: E402
from jordan_tender_monitor.tests import (harness, test_browser,  # noqa: E402
                                         test_capture, test_extraction,
                                         test_pipeline, test_portals_api)


def main() -> int:
    print("Jordan Tender Intelligence Monitor -- offline test suite")
    print(f"State redirected to: {_TMP}")
    print(f"Real database ({config.SEEN_DB.name}) is not opened by any test.")

    harness.run_suite("Extraction, parsing and the quality gate",
                      test_extraction.TESTS)
    harness.run_suite("Pipeline: filter, score, dedupe, report, deliver",
                      test_pipeline.TESTS)
    harness.run_suite("REST API portal modules", test_portals_api.TESTS)
    harness.run_suite("Capture and the portal registry", test_capture.TESTS)
    harness.run_suite("The headless-browser path (UNGM)", test_browser.TESTS)

    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
