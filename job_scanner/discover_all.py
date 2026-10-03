#!/usr/bin/env python3
"""Run endpoint discovery across every employer, into one pasteable file.

    python discover_all.py

Written so the person running it has one command to type and one file to hand
back, rather than fifteen commands and fifteen blocks to collect. It reads
sources.yaml, opens each employer's careers page in a headless browser, and
appends every discovery report to runs/discovery_<date>.txt.

Nothing here edits sources.yaml. Discovery reports what it saw; deciding what
that means, and what `verified` may honestly claim, is a separate step done by
someone reading the output.

Skips sidra (permanently disabled -- a stale mirror whose newest vacancy closed
in 2019) and recruiter_alerts (a mailbox, not a website).
"""

from __future__ import annotations

import datetime as _dt
import io
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Between sites, not just between requests. Fifteen browsers opened
# back-to-back is still fifteen employers being visited.
DELAY_BETWEEN_SITES = 3.0


def main() -> int:
    # find_spec rather than a probe import: pyflakes does not honour noqa, and
    # the repository's CI lints with pyflakes.
    import importlib.util

    if importlib.util.find_spec("playwright") is None:
        print(
            "Playwright is not installed. Run these three, then try again:\n"
            "  python -m pip install -r requirements-browser.txt\n"
            "  python -m playwright install chromium\n"
            "  python -m playwright install-deps      # Linux only, needs sudo",
            file=sys.stderr,
        )
        return 3

    from discover_playwright import discover

    config = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    targets = [
        source
        for source in config["sources"]
        if source.get("careers_url")
        and not source.get("permanently_disabled")
        and source.get("platform") != "imap"
    ]

    out_dir = ROOT / "runs"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"discovery_{_dt.date.today().isoformat()}.txt"

    header = (
        f"Endpoint discovery — {_dt.datetime.now().isoformat(timespec='seconds')}\n"
        f"{len(targets)} employer(s) to probe\n"
        + "=" * 72
        + "\n"
    )
    out_path.write_text(header, encoding="utf-8")
    print(header)

    results: list[tuple[str, str]] = []

    for index, source in enumerate(targets, start=1):
        key, url = source["key"], source["careers_url"]
        print(f"[{index}/{len(targets)}] {key} — {url}", flush=True)

        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                code = discover(url, key, wait=6000, timeout=45000)
        except Exception as exc:                      # one bad site must not end the run
            code = 3
            buffer.write(f"\nDiscovery raised {type(exc).__name__}: {exc}\n")

        verdict = {0: "FOUND SOMETHING", 1: "nothing found", 2: "page did not load"}.get(
            code, "tool error"
        )
        results.append((key, verdict))
        print(f"          -> {verdict}\n", flush=True)

        with out_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n\n{'#' * 72}\n### {key}  ({verdict})\n### {url}\n{'#' * 72}\n")
            handle.write(buffer.getvalue())

        if index < len(targets):
            time.sleep(DELAY_BETWEEN_SITES)

    summary = ["", "=" * 72, "SUMMARY", "=" * 72]
    for key, verdict in results:
        summary.append(f"  {key:<16} {verdict}")
    summary += [
        "",
        f"Full output written to: {out_path}",
        "",
        "Send that file back. It contains only what the public careers pages",
        "served -- no credentials, no personal data.",
    ]
    text = "\n".join(summary)
    print(text)
    with out_path.open("a", encoding="utf-8") as handle:
        handle.write("\n" + text + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
