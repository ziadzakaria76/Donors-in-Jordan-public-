#!/usr/bin/env python3
"""
Summarise an Android instrumented-test run for the job summary.

Kept as a file rather than inlined in the workflow on purpose. A Python
heredoc inside a YAML block scalar has to sit at column 1 to terminate, which
ends the block scalar instead -- GitHub then refuses the whole workflow, and it
does so without a red cross anywhere, because a workflow it cannot parse is a
workflow it does not run. That has happened in this repository before.

Usage:
    android_test_summary.py <results-dir> [api-level]

Reads the JUnit XML the Gradle connected-test task writes and prints markdown.
Exits 0 always: this reports, it does not judge. The Gradle task's own exit
code decides whether the job failed.
"""

from __future__ import annotations

import glob
import os
import sys
import xml.etree.ElementTree as ET

MAX_LISTED = 40


def main(argv: list[str]) -> int:
    results_dir = argv[1] if len(argv) > 1 else ""
    api_level = argv[2] if len(argv) > 2 else "?"

    print(f"### Instrumented tests — API {api_level}")
    print()

    # Recursive. AGP nests connected-test results under a build-type
    # directory (.../connected/debug/TEST-*.xml), and looking only in the top
    # level reported "no results" for a run where 26 tests had executed and 2
    # had failed. Wrong on its own terms, and the wrong direction of wrong:
    # the summary is the part someone reads instead of the log.
    files = sorted(glob.glob(os.path.join(results_dir, "**", "*.xml"),
                             recursive=True))
    if not files:
        # An absent report is not a pass. Say which it is, loudly, because a
        # silent "0 failures" from a run where nothing executed reads exactly
        # like success.
        print("**No result XML was written.** The emulator or the build failed "
              "before any test ran, so this is UNTESTED, not passing.")
        return 0

    total = failures = errors = skipped = 0
    bad: list[str] = []

    for path in files:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            print(f"- Could not read `{os.path.basename(path)}`: {exc}")
            continue
        total += int(root.get("tests") or 0)
        failures += int(root.get("failures") or 0)
        errors += int(root.get("errors") or 0)
        skipped += int(root.get("skipped") or 0)
        for case in root.iter("testcase"):
            for problem in case:
                if problem.tag in ("failure", "error"):
                    bad.append(f"{case.get('classname')}.{case.get('name')}")

    print(f"**{total} tests** — {failures} failed, {errors} errored, "
          f"{skipped} skipped.")
    print()

    if total == 0:
        print("A report was written but it contains no tests. Treat this as "
              "untested: something ran and found nothing to run.")
        return 0

    if bad:
        print("Failed:")
        print()
        print("```")
        for name in bad[:MAX_LISTED]:
            print(name)
        # No silent caps: if the list is trimmed, say so with both numbers.
        if len(bad) > MAX_LISTED:
            print(f"... and {len(bad) - MAX_LISTED} more "
                  f"({len(bad)} altogether)")
        print("```")
        print()
        print("Full reports, a screenshot of the screen at the end, and the "
              "device log are in this run's artifacts.")
    else:
        print("All passed. This is the only place the Keystore-backed token "
              "store, Room's generated SQL, and the screens themselves are "
              "exercised at all.")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
