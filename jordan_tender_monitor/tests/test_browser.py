"""
The headless-browser path, and the one portal that needs it.

UNGM is the richest Jordan source and the only portal that cannot be read over
plain HTTP -- its listing is assembled client-side, so a fetch returns 141 KB of
navigation with not one notice in it. That makes Playwright load-bearing for
UNGM and irrelevant to the other twelve, which is exactly the shape that goes
wrong: an optional dependency that silently becomes mandatory, or a missing one
that produces a traceback instead of an instruction.

Nothing here launches a browser. Playwright is deliberately NOT installed in the
test environment -- if these tests needed it, the "optional" claim would be
false. The rendering path is exercised against a fake playwright module, so the
error translation is covered whether or not the real package is present.
"""

from __future__ import annotations

import importlib.machinery
import io
import sys
import types
from contextlib import contextmanager
from pathlib import Path

from jordan_tender_monitor.portals import base, browser, giz, harvester, ungm
from jordan_tender_monitor.portals.base import PortalError

from .harness import check, check_eq

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# A fake playwright, so the render path is testable without ~400 MB of browser
# ---------------------------------------------------------------------------

class _FakePage:
    def __init__(self, html: str, selector_appears: bool = True):
        self.html = html
        self.selector_appears = selector_appears
        self.waited_for: list[str] = []
        self.settled_ms = 0
        self.goto_url: str | None = None
        self.timeout_ms: int | None = None

    def set_default_timeout(self, ms):
        self.timeout_ms = ms

    def goto(self, url, **kwargs):
        self.goto_url = url

    def wait_for_selector(self, selector, timeout=None):
        self.waited_for.append(selector)
        if not self.selector_appears:
            raise RuntimeError("Timeout 15000ms exceeded waiting for selector")

    def wait_for_timeout(self, ms):
        self.settled_ms += ms

    def content(self):
        return self.html


class _FakeBrowser:
    def __init__(self, page):
        self.page = page
        self.closed = False
        self.new_page_kwargs = None

    def new_page(self, **kwargs):
        self.new_page_kwargs = kwargs
        return self.page

    def close(self):
        self.closed = True


class _FakePlaywright:
    """Stands in for the object `sync_playwright()` yields."""

    def __init__(self, page=None, launch_error: Exception | None = None):
        self.page = page
        self.launch_error = launch_error
        self.browser: _FakeBrowser | None = None
        self.launch_args = None
        self.chromium = self

    def launch(self, **kwargs):
        self.launch_args = kwargs
        if self.launch_error is not None:
            raise self.launch_error
        self.browser = _FakeBrowser(self.page)
        return self.browser

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@contextmanager
def _fake_playwright(page=None, launch_error: Exception | None = None):
    """Install a fake `playwright.sync_api` for the duration of a block."""
    fake = _FakePlaywright(page=page, launch_error=launch_error)

    package = types.ModuleType("playwright")
    # find_spec() raises ValueError on a module with no __spec__, and
    # browser.available() would then report False for a package that is very
    # much importable. Give the fake a real spec so available() sees it.
    package.__spec__ = importlib.machinery.ModuleSpec("playwright", None)
    api = types.ModuleType("playwright.sync_api")
    api.__spec__ = importlib.machinery.ModuleSpec("playwright.sync_api", None)
    api.sync_playwright = lambda: fake
    package.sync_api = api

    saved = {name: sys.modules.get(name)
             for name in ("playwright", "playwright.sync_api")}
    sys.modules["playwright"] = package
    sys.modules["playwright.sync_api"] = api
    try:
        yield fake
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


@contextmanager
def _no_playwright():
    """Make the import fail, whatever is really installed."""
    saved = {name: sys.modules.get(name)
             for name in ("playwright", "playwright.sync_api")}
    sys.modules["playwright"] = None          # import raises ImportError
    sys.modules["playwright.sync_api"] = None
    try:
        yield
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


# ---------------------------------------------------------------------------
# Optionality
# ---------------------------------------------------------------------------

def test_playwright_stays_out_of_the_main_requirements():
    """A Windows deployment must not be forced to pull ~400 MB for one portal."""
    def installed(path: Path) -> list[str]:
        """The lines pip would actually act on -- comments do not install."""
        return [line.strip() for line in io.open(path, encoding="utf-8")
                if line.strip() and not line.strip().startswith("#")]

    main = installed(ROOT / "requirements.txt")
    extra = installed(ROOT / "requirements-browser.txt")
    check(not any("playwright" in line.lower() for line in main),
          "browser: requirements.txt installs no playwright",
          f"got {[l for l in main if 'playwright' in l.lower()]}")
    check(any("playwright" in line.lower() for line in extra),
          "browser: requirements-browser.txt does install it")
    check(len(extra) == 1,
          "browser: and nothing else -- the optional file stays one package",
          f"got {extra}")


def test_importing_the_portals_does_not_import_playwright():
    """An optional dependency imported at module scope is not optional.

    portals/__init__ imports every module including ungm, so a top-level
    `import playwright` there would make the whole system refuse to start
    without it -- and the other twelve portals do not need it at all.
    """
    import jordan_tender_monitor.portals as _registry
    check(_registry.MODULES and "playwright" not in sys.modules,
          "browser: importing the portal registry does not pull in playwright")


def test_only_ungm_depends_on_the_browser():
    import inspect

    from jordan_tender_monitor import portals as registry

    users = sorted(key for key, module in registry.MODULES.items()
                   if "browser." in inspect.getsource(module))
    check_eq(users, ["ungm"],
             "browser: exactly one portal takes the headless-browser dependency")


# ---------------------------------------------------------------------------
# Degrading when it is absent
# ---------------------------------------------------------------------------

def test_a_missing_browser_is_an_instruction_not_a_traceback():
    original = browser.available
    try:
        browser.available = lambda: False
        try:
            ungm._fetch_rendered(ungm.LISTING)
            check(False, "browser: a missing browser must raise PortalError")
        except PortalError as exc:
            check("pip install -r requirements-browser.txt" in exc.reason,
                  "browser: the reason names the exact install command")
            check("playwright install chromium" in exc.reason,
                  "browser: and the browser-download command too")
            check_eq(exc.url, ungm.LISTING,
                     "browser: the URL to check by hand is carried")
    finally:
        browser.available = original


def test_render_says_how_to_install_when_the_import_fails():
    with _no_playwright():
        check(not browser.available(),
              "browser: available() reports False when playwright is absent")
        try:
            browser.render("https://www.ungm.org/Public/Notice")
            check(False, "browser: render() must raise when playwright is absent")
        except PortalError as exc:
            check("not installed" in exc.reason,
                  "browser: render() diagnoses the missing package")
            check("requirements-browser.txt" in exc.reason,
                  "browser: and names the install file")


def test_an_uninstalled_chromium_is_diagnosed_separately_from_a_missing_package():
    """`pip install playwright` is not enough; the browser is a second download.

    Two different fixes, so they must not share one error message.
    """
    error = Exception(
        "BrowserType.launch: Executable doesn't exist at "
        "/root/.cache/ms-playwright/chromium-1091/chrome-linux/chrome\n"
        "Please run the following command to download new browsers:\n"
        "playwright install")
    with _fake_playwright(launch_error=error):
        try:
            browser.render("https://www.ungm.org/Public/Notice")
            check(False, "browser: a missing chromium must raise")
        except PortalError as exc:
            check("browser is not" in exc.reason,
                  "browser: the diagnosis is about the BROWSER, not the package",
                  f"got {exc.reason!r}")
            check("playwright install chromium" in exc.reason,
                  "browser: and gives the one command that fixes it")


def test_an_unexpected_render_failure_names_its_exception_type():
    with _fake_playwright(launch_error=RuntimeError("the sandbox refused to start")):
        try:
            browser.render("https://www.ungm.org/Public/Notice")
            check(False, "browser: an unexpected failure must raise PortalError")
        except PortalError as exc:
            check("RuntimeError" in exc.reason,
                  "browser: the exception type is reported so it can be debugged")
            check("sandbox refused" in exc.reason,
                  "browser: along with the message")


def test_ungm_failing_leaves_the_other_portals_alone():
    """The whole point of keeping this optional: one portal's dependency.

    A run on a machine without Playwright must report UNGM as unavailable with
    an install instruction, and report the other twelve normally.
    """
    from jordan_tender_monitor import config
    from jordan_tender_monitor import portals as registry
    from jordan_tender_monitor.agents import scraper

    class _Good:
        @staticmethod
        def fetch_tenders():
            return [base.build_record(portal="worldbank",
                                      title="Advisory Services, Amman, Jordan",
                                      url="https://e.org/ok")]

    original_modules = dict(registry.MODULES)
    original_enabled = dict(config.ENABLED_PORTALS)
    original_available = browser.available
    try:
        browser.available = lambda: False
        registry.MODULES.clear()
        registry.MODULES.update({"ungm": ungm, "worldbank": _Good})
        config.ENABLED_PORTALS.clear()
        config.ENABLED_PORTALS.update({"ungm": True, "worldbank": True})
        result = scraper.scrape()
    finally:
        browser.available = original_available
        registry.MODULES.clear()
        registry.MODULES.update(original_modules)
        config.ENABLED_PORTALS.clear()
        config.ENABLED_PORTALS.update(original_enabled)

    by_key = {h.key: h for h in result.health}
    check_eq(by_key["ungm"].status, "unavailable",
             "browser: UNGM reports unavailable, not a crash")
    check("requirements-browser.txt" in by_key["ungm"].reason,
          "browser: and the report tells you how to fix it",
          f"got {by_key['ungm'].reason!r}")
    check_eq(len(result.records), 1,
             "browser: the other portal's records are unaffected")


# ---------------------------------------------------------------------------
# Rendering, when it is present
# ---------------------------------------------------------------------------

def test_render_returns_the_rendered_dom_and_closes_the_browser():
    html = io.open(FIXTURES / "drupal_views.html", encoding="utf-8").read()
    page = _FakePage(html)
    with _fake_playwright(page=page) as fake:
        got = browser.render("https://www.ungm.org/Public/Notice",
                             wait_for=ungm.ROW_HINT, settle_ms=1500)

    check_eq(got, html, "browser: the rendered DOM is returned")
    check_eq(page.goto_url, "https://www.ungm.org/Public/Notice",
             "browser: the requested URL is the one loaded")
    check_eq(page.waited_for, [ungm.ROW_HINT],
             "browser: it waits for the row selector before reading")
    check_eq(page.settled_ms, 1500,
             "browser: and still settles afterwards, for staged rendering")
    check(fake.browser is not None and fake.browser.closed,
          "browser: the browser is closed even on the happy path")
    check("--disable-dev-shm-usage" in (fake.launch_args or {}).get("args", []),
          "browser: launched with the flag CI containers need")


def test_a_selector_that_never_appears_is_a_hint_not_a_failure():
    """A renamed class must degrade to a weak result, not a dead portal.

    The cascade can diagnose 'the page rendered but the rows look wrong'. It
    cannot diagnose anything at all if the wait times out into an exception.
    """
    html = io.open(FIXTURES / "drupal_views.html", encoding="utf-8").read()
    page = _FakePage(html, selector_appears=False)
    with _fake_playwright(page=page):
        got = browser.render("https://www.ungm.org/Public/Notice",
                             wait_for="div.class-that-was-renamed", settle_ms=100)
    check_eq(got, html,
             "browser: the DOM is read anyway when the hint selector never appears")
    check_eq(page.settled_ms, 100, "browser: the settle delay still ran")


def test_ungm_routes_its_rendered_html_through_the_cascade():
    """Rendering is a fetch strategy, not a parallel pipeline.

    A portal that rendered its own HTML and then parsed it its own way would
    miss every fix made to the cascade -- the date gate, the value rules, the
    country filter.
    """
    html = io.open(FIXTURES / "drupal_views.html", encoding="utf-8").read()
    page = _FakePage(html)

    def fetch_via_browser(url):
        return browser.render(url, wait_for=ungm.ROW_HINT, settle_ms=0)

    spec = harvester.HtmlSpec(key="ungm", urls=[ungm.LISTING],
                              selectors=ungm.SPEC.selectors,
                              anchor_hint=ungm.SPEC.anchor_hint,
                              fetcher=fetch_via_browser)
    with _fake_playwright(page=page):
        results = harvester.capture(spec)

    check_eq(len(results), 1, "browser: capture works through the rendered fetcher")
    url, captured, layers = results[0]
    check(bool(captured), "browser: --capture sees the rendered DOM, not the shell")
    check(any(layer.rows for layer in layers),
          "browser: the cascade runs over the rendered DOM")


def test_ungm_selectors_come_from_the_rendered_dom():
    """And 'table tbody tr' is kept out, because it matched the date picker.

    On the rendered page that selector found six rows: the Su/Mo/Tu/We/Th/Fr/Sa
    cells of a calendar widget. Selectors run before the class-independent
    layers, so an over-broad one short-circuits the layer that would have
    worked -- the exact failure the quality gate exists to catch. Handing it
    one on purpose is not a reasonable thing to do.
    """
    check_eq(ungm.SPEC.selectors[0], "div.dataRow.notice-table",
             "ungm: the selector derived from the live rendered DOM comes first")
    check(not any("table tbody tr" in s for s in ungm.SPEC.selectors),
          "ungm: the date-picker selector is NOT in the list",
          f"got {ungm.SPEC.selectors}")


def test_ungm_declares_the_rendered_fetcher_and_filters_to_jordan():
    check(ungm.SPEC.fetcher is ungm._fetch_rendered,
          "ungm: the spec uses the rendered fetcher")
    check_eq(ungm.SPEC.urls, [ungm.LISTING],
             "ungm: the dead POST search endpoint is no longer a source")
    check(ungm.SPEC.filter_to_jordan,
          "ungm: the rendered listing is worldwide, so it must be filtered")
    check("playwright" in ungm.SPEC.notes.lower() or "browser" in ungm.SPEC.notes.lower(),
          "ungm: the extra dependency is visible in the portal's notes")


# ---------------------------------------------------------------------------
# The environment this actually runs in
# ---------------------------------------------------------------------------

def test_the_workflow_installs_the_browser():
    """UNGM runs from a phone via GitHub Actions, or it does not run at all.

    Without this step the richest Jordan source reports 'unavailable' forever
    in the only environment the system is actually used from -- and it would
    look like a site problem, not a missing install line.
    """
    workflow = io.open(ROOT.parent / ".github" / "workflows" / "monitor.yml",
                       encoding="utf-8").read()
    check("requirements-browser.txt" in workflow,
          "workflow: the optional browser requirements are installed")
    check("playwright install" in workflow,
          "workflow: and chromium itself is downloaded")


def test_giz_dropped_the_page_that_carried_no_listing():
    """--capture showed giz.de/en/partner/contractor/tenders is an info page.

    Its derived selectors were main-menu__container (74 blocks) and
    main-menu__item (33): pure navigation. Kept in the list it would fail on
    every run and make a working portal look half-broken.
    """
    urls = giz.SPEC.urls
    check_eq(len(urls), 1, "giz: one source URL, the German portal")
    check("ausschreibungen.giz.de" in urls[0],
          "giz: and it is the ausschreibungen portal")
    check(not any("giz.de/en/partner" in u for u in urls),
          "giz: the English information page is no longer fetched")


TESTS = [
    test_playwright_stays_out_of_the_main_requirements,
    test_importing_the_portals_does_not_import_playwright,
    test_only_ungm_depends_on_the_browser,
    test_a_missing_browser_is_an_instruction_not_a_traceback,
    test_render_says_how_to_install_when_the_import_fails,
    test_an_uninstalled_chromium_is_diagnosed_separately_from_a_missing_package,
    test_an_unexpected_render_failure_names_its_exception_type,
    test_ungm_failing_leaves_the_other_portals_alone,
    test_render_returns_the_rendered_dom_and_closes_the_browser,
    test_a_selector_that_never_appears_is_a_hint_not_a_failure,
    test_ungm_routes_its_rendered_html_through_the_cascade,
    test_ungm_selectors_come_from_the_rendered_dom,
    test_ungm_declares_the_rendered_fetcher_and_filters_to_jordan,
    test_the_workflow_installs_the_browser,
    test_giz_dropped_the_page_that_carried_no_listing,
]
