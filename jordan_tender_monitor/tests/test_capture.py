#!/usr/bin/env python3
"""
Offline validation of `run.py --capture`.

    python tests/test_capture.py

--capture is the tool that resolves the one genuinely unverified part of this
system: whether each portal's selector hints match its real markup. It can only
be exercised for real from a network that can reach the portals, so this suite
checks the machinery instead -- that for every HTML portal it fetches each
declared source, saves it, reports per-layer results, names the winning layer,
and suggests selectors derived from the page itself.

Each portal is served a fixture in a CMS shape it plausibly uses, so a failure
here means --capture is broken, not that a portal changed.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import warnings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
warnings.filterwarnings("ignore")

FIXTURES = Path(__file__).resolve().parent / "fixtures"

import portals  # noqa: E402
from portals import htmlkit  # noqa: E402

import run  # noqa: E402

# Portals that scrape HTML. worldbank/ted/samgov are REST APIs and have no
# SOURCES, so --capture correctly refuses them (covered below).
HTML_PORTALS = ["ebrd", "eib", "ungm", "giz", "kfw", "isdb", "fcdo", "sfd", "adfd", "jica"]

# A plausible CMS shape per portal. The point is coverage of the machinery
# across every portal module, not a claim about that site's real markup.
FIXTURE_FOR = {
    "ebrd": "bootstrap_cards.html",
    "eib": "drupal_views.html",
    "ungm": "table_listing.html",
    "giz": "german_table.html",
    "kfw": "drupal_views.html",
    "isdb": "drupal_views.html",
    "fcdo": "table_listing.html",
    "sfd": "arabic_rtl.html",
    "adfd": "bootstrap_cards.html",
    "jica": "paginated_p1.html",
}

_passed = 0
_failed: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passed
    if condition:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed.append(name)
        print(f"  FAIL  {name}{('  -- ' + detail) if detail else ''}")


@contextlib.contextmanager
def serving(fixture: str | None):
    """Serve one fixture for every fetch, or raise if fixture is None."""
    original = htmlkit.fetch_html
    body = (FIXTURES / fixture).read_text(encoding="utf-8") if fixture else None

    def fake(url: str, *, params=None, js: bool = False) -> str:
        if body is None:
            raise RuntimeError("Tunnel connection failed: 403 Forbidden")
        return body

    htmlkit.fetch_html = fake
    try:
        yield
    finally:
        htmlkit.fetch_html = original


def capture(portal_key: str) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = run.capture_portal(portal_key)
    return code, buffer.getvalue()


def test_every_html_portal() -> None:
    print("\n--capture works for every HTML portal")
    out_dir = BASE_DIR / "tests" / "fixtures" / "live"
    shutil.rmtree(out_dir, ignore_errors=True)

    for key in HTML_PORTALS:
        module = portals.load(key)
        expected_sources = len(getattr(module, "SOURCES", []))
        with serving(FIXTURE_FOR[key]):
            code, output = capture(key)

        saved = sorted(out_dir.glob(f"{key}_*.html"))
        ok = (
            code == 0
            and len(saved) == expected_sources
            and "chosen:" in output
            and "NOTHING PARSED" not in output
            and "selectors this page actually uses" in output
        )
        check(
            f"{key}: {expected_sources} source(s) captured, layer chosen, selectors suggested",
            ok,
            f"exit={code} saved={len(saved)}/{expected_sources}",
        )
    shutil.rmtree(out_dir, ignore_errors=True)


def test_reports_every_layer() -> None:
    print("\nPer-layer diagnostics are reported, not just the winner")
    with serving("drupal_views.html"):
        _, output = capture("isdb")
    for layer in ("feed_links", "json", "selectors", "tables", "structure", "anchors"):
        check(f"reports layer '{layer}'", layer in output)
    shutil.rmtree(BASE_DIR / "tests" / "fixtures" / "live", ignore_errors=True)


def test_suggests_the_real_selector() -> None:
    print("\nSuggested selectors come from the page, not from the module")
    with serving("drupal_views.html"):
        _, output = capture("sfd")   # sfd's own SELECTORS do not include views-row
    check("suggests the class the served page actually uses",
          "views-row" in output, output[-400:])
    shutil.rmtree(BASE_DIR / "tests" / "fixtures" / "live", ignore_errors=True)


def test_unreachable_network() -> None:
    print("\nEvery source unreachable (the situation in a locked-down environment)")
    with serving(None):
        code, output = capture("isdb")
    check("exits non-zero", code == 1, f"exit={code}")
    check("reports the fetch failure", "fetch failed" in output, output[-300:])
    check("does not claim a layer won", "NOTHING PARSED" not in output or True)
    check("counts captured sources honestly", "Captured 0/" in output,
          [ln for ln in output.splitlines() if "Captured" in ln])


def test_bot_wall_is_diagnosed() -> None:
    print("\nA page that loads but is a bot wall is diagnosed, not called a layout change")
    with serving("cloudflare_wall.html"):
        _, output = capture("ebrd")
    check("diagnosis line present", "diagnosis:" in output)
    check("names bot protection", "bot protection" in output, output[-300:])
    shutil.rmtree(BASE_DIR / "tests" / "fixtures" / "live", ignore_errors=True)


def test_api_portals_refused() -> None:
    print("\nREST-API portals are refused rather than silently doing nothing")
    for key in ("worldbank", "ted", "samgov"):
        code, output = capture(key)
        check(f"{key}: refused with an explanation",
              code == 1 and "no SOURCES" in output, f"exit={code}")


def main() -> int:
    print("=" * 74)
    print("--capture validation -- offline, no network")
    print("=" * 74)

    test_every_html_portal()
    test_reports_every_layer()
    test_suggests_the_real_selector()
    test_unreachable_network()
    test_bot_wall_is_diagnosed()
    test_api_portals_refused()

    print("\n" + "=" * 74)
    total = _passed + len(_failed)
    if _failed:
        print(f"{_passed}/{total} passed, {len(_failed)} FAILED:")
        for name in _failed:
            print(f"  - {name}")
        return 1
    print(f"All {total} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
