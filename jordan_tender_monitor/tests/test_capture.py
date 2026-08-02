"""
Capture tests.

--capture is how an unverified selector hint gets confirmed against a live page
in one command, so two properties matter:

  1. It works for EVERY HTML portal, including the ones with custom fetch logic.
     A portal with a bespoke fetcher is exactly the one most easily left out of
     a diagnostic by accident, and it is the one that most needs the diagnostic.

  2. It fails HONESTLY when a source is unreachable -- reporting the failure
     rather than an empty success, which would read as "this portal has no
     Jordan notices".

No network is used: the fetcher is replaced with one that serves fixtures or
raises.
"""

from __future__ import annotations

import io
from pathlib import Path

from jordan_tender_monitor import config, portals
from jordan_tender_monitor.portals import harvester
from jordan_tender_monitor.portals.base import PortalError
from jordan_tender_monitor.portals.harvester import HtmlSpec

from .harness import check, check_eq

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _serve(name: str):
    html = io.open(FIXTURES / name, encoding="utf-8").read()
    return lambda url: html


def _unreachable(reason: str = "transport error - ConnectionError (host blocked)"):
    def fetcher(url):
        raise PortalError(reason, url)
    return fetcher


# ---------------------------------------------------------------------------


def test_every_html_portal_is_capturable():
    html_keys = set(portals.html_portals())
    expected = {"ungm", "ebrd", "eib", "giz", "kfw", "isdb", "sfd", "adfd", "jica"}
    check_eq(html_keys, expected, "capture: all nine HTML portals expose capture()")

    for key, module in portals.html_portals().items():
        check(callable(getattr(module, "capture", None)),
              f"capture: {key} has a callable capture()")
        check(hasattr(module, "SPEC"), f"capture: {key} declares a SPEC")
        check(bool(module.SPEC.urls), f"capture: {key} declares at least one URL")


def test_ungm_with_custom_fetcher_is_included():
    """UNGM posts to a search endpoint rather than fetching a page.

    A capture command built only around plain GETs would silently omit it --
    and UNGM is the richest Jordan source, so omitting it would matter most.
    """
    from jordan_tender_monitor.portals import ungm

    check("ungm" in portals.html_portals(),
          "capture: UNGM is capturable despite its custom fetcher")
    check(ungm.SPEC.fetcher is not None, "capture: UNGM does have a custom fetcher")

    spec = HtmlSpec(key="ungm", urls=[ungm.SEARCH], selectors=ungm.SPEC.selectors,
                    anchor_hint=ungm.SPEC.anchor_hint,
                    fetcher=_serve("nextjs_json.html"))
    results = harvester.capture(spec)
    check_eq(len(results), 1, "capture: the custom-fetcher portal returns a result")
    url, html, layers = results[0]
    check(bool(html), "capture: content came back through the custom fetcher")
    check(any(layer.rows for layer in layers), "capture: layers found rows")


def test_capture_reports_every_layer():
    spec = HtmlSpec(key="test", urls=["https://e.org/list"],
                    selectors=[".views-row"], fetcher=_serve("drupal_views.html"))
    results = harvester.capture(spec)
    url, html, layers = results[0]

    names = [layer.layer for layer in layers]
    for expected in ("feed", "embedded-json", "selectors", "table",
                     "structural", "anchor-pattern"):
        check(expected in names, f"capture: the {expected} layer is reported")

    winners = [layer for layer in layers
               if layer.rows and layer.quality >= 0.36]
    check(winners, "capture: at least one layer clears the gate")
    check(any(layer.quality > 0 for layer in layers),
          "capture: per-layer quality scores are reported")
    check(any(len(layer.rows) > 0 for layer in layers),
          "capture: per-layer row counts are reported")


def test_capture_fails_honestly_when_unreachable():
    spec = HtmlSpec(key="test", urls=["https://blocked.example/list"],
                    fetcher=_unreachable())
    results = harvester.capture(spec)
    check_eq(len(results), 1, "capture: an unreachable source still returns a result")
    url, html, layers = results[0]
    check_eq(html, "", "capture: no content is invented")
    check_eq(layers[0].layer, "error", "capture: the result is marked as an error")
    check("transport error" in layers[0].note,
          "capture: the diagnosed reason is carried through")
    check(not layers[0].rows, "capture: no rows are reported for a failed fetch")


def test_capture_distinguishes_bot_wall_from_layout_change():
    wall = harvester.capture(HtmlSpec(key="t", urls=["https://e.org/x"],
                                      fetcher=_serve("cloudflare_wall.html")))
    _, html, layers = wall[0]
    from jordan_tender_monitor.portals.htmlkit import diagnose
    check("bot wall" in diagnose(html, []),
          "capture: a bot wall is diagnosed as a bot wall")

    shell = harvester.capture(HtmlSpec(key="t", urls=["https://e.org/x"],
                                       fetcher=_serve("js_shell.html")))
    _, html2, _ = shell[0]
    check("JavaScript shell" in diagnose(html2, []),
          "capture: a JS shell is diagnosed distinctly")


def test_harvest_tolerates_one_failing_source():
    """Several portals publish across two sites; one failing must not kill both."""
    calls = {"n": 0}
    good = io.open(FIXTURES / "drupal_views.html", encoding="utf-8").read()

    def flaky(url):
        calls["n"] += 1
        if "broken" in url:
            raise PortalError("HTTP 404 - the URL has moved", url)
        return good

    spec = HtmlSpec(key="ebrd", urls=["https://broken.example/a",
                                      "https://good.example/b"],
                    selectors=[".views-row"], fetcher=flaky,
                    filter_to_jordan=True)
    original = config.FOLLOW_PAGINATION
    try:
        config.FOLLOW_PAGINATION = False
        records = harvester.harvest(spec)
    finally:
        config.FOLLOW_PAGINATION = original

    check(records, "harvest: the working source still produces records")
    check(calls["n"] >= 2, "harvest: both sources were attempted")


def test_harvest_raises_when_every_source_fails():
    spec = HtmlSpec(key="ebrd", urls=["https://a.example", "https://b.example"],
                    fetcher=_unreachable("HTTP 403 - blocked"))
    try:
        harvester.harvest(spec)
        check(False, "harvest: a fully failed portal must raise")
    except PortalError as exc:
        check(True, "harvest: a fully failed portal raises PortalError")
        check("403" in exc.reason, "harvest: the diagnosed reason is preserved")
        check(exc.url, "harvest: the URL to check by hand is carried")


def test_portal_registry_is_complete():
    check_eq(len(portals.MODULES), 13, "registry: all thirteen portals registered")
    for key, module in portals.MODULES.items():
        check(callable(getattr(module, "fetch_tenders", None)),
              f"registry: {key} exposes fetch_tenders()")
        check(key in config.PORTAL_NAMES, f"registry: {key} has a display name")
        check(key in config.PORTAL_TIERS, f"registry: {key} has a reliability tier")
        check(bool(portals.source_urls(key)), f"registry: {key} declares source URLs")


def test_kfw_points_at_gtai_not_kfw_de():
    """KfW does not publish notices on its own site -- GTAI does.

    Pointing at kfw.de makes this portal report 'unavailable' forever while
    looking like an honest failure.
    """
    urls = " ".join(portals.source_urls("kfw"))
    check("gtai.de" in urls, "kfw: the source is gtai.de")
    check("kfw.de" not in urls, "kfw: kfw.de is NOT used as a tender source")


TESTS = [
    test_every_html_portal_is_capturable,
    test_ungm_with_custom_fetcher_is_included,
    test_capture_reports_every_layer,
    test_capture_fails_honestly_when_unreachable,
    test_capture_distinguishes_bot_wall_from_layout_change,
    test_harvest_tolerates_one_failing_source,
    test_harvest_raises_when_every_source_fails,
    test_portal_registry_is_complete,
    test_kfw_points_at_gtai_not_kfw_de,
]
