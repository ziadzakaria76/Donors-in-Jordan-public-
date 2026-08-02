#!/usr/bin/env python3
"""
Run every offline test suite.

    python tests/run_all.py

No network, no credentials, no side effects on data/ or output/. Run this after
touching anything in portals/ or agents/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TESTS = ["test_extraction.py", "test_pipeline.py", "test_capture.py"]
HERE = Path(__file__).resolve().parent


def main() -> int:
    results: list[tuple[str, int, str]] = []
    for name in TESTS:
        print(f"\n{'#' * 74}\n# {name}\n{'#' * 74}")
        proc = subprocess.run(
            [sys.executable, str(HERE / name)], capture_output=True, text=True
        )
        sys.stdout.write(proc.stdout)
        if proc.stderr.strip():
            sys.stderr.write(proc.stderr)
        summary = next(
            (ln for ln in reversed(proc.stdout.splitlines()) if "passed" in ln), "no summary"
        )
        results.append((name, proc.returncode, summary))

    print(f"\n{'=' * 74}\nOverall\n{'=' * 74}")
    for name, code, summary in results:
        print(f"  {'PASS' if code == 0 else 'FAIL'}  {name:<22} {summary}")
    return 0 if all(code == 0 for _, code, _ in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
