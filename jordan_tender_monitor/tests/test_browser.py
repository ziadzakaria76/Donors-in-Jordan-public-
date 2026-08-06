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

from jordan_tender_monitor import portals
from jordan_tender_monitor.portals import base, browser, harvester, ungm
from jordan_tender_monitor.portals.base import PortalError

from .harness import check, check_eq

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# A fake playwright, so the render path is testable without ~400 MB of browser
# ---------------------------------------------------------------------------

class _FakePage:
    def __init__(self, html: str, selector_appears: bool = True,
                 row_counts: list[int] | None = None):
        self.html = html
        self.selector_appears = selector_appears
        self.waited_for: list[str] = []
        self.settled_ms = 0
        self.goto_url: str | None = None
        self.timeout_ms: int | None = None
        # Successive row counts, one per count() call, simulating a listing
        # that loads more as it is scrolled. The last value repeats forever.
        self.row_counts = list(row_counts or [0])
        self.counted = 0
        self.scrolls = 0
        self.wheeled = 0
        self.scroll_into_view_fails = False

    def row_count(self):
        value = self.row_counts[min(self.counted, len(self.row_counts) - 1)]
        self.counted += 1
        return value

    def locator(self, selector):
        self.locator_selector = selector
        return _FakeLocator(self, selector)

    class _Mouse:
        def __init__(self, page):
            self.page = page

        def wheel(self, dx, dy):
            self.page.scrolls += 1
            self.page.wheeled += 1

    @property
    def mouse(self):
        return _FakePage._Mouse(self)

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


class _FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    def count(self):
        return self.page.row_count()

    @property
    def last(self):
        return self

    def scroll_into_view_if_needed(self, timeout=None):
        if self.page.scroll_into_view_fails:
            raise RuntimeError("element is not attached to the DOM")
        self.page.scrolls += 1


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


def test_the_browser_dependency_stays_contained():
    """One portal needs it, and a second was tried and rejected on evidence.

    ADFD looked like the same client-rendered shape as UNGM, so it was wired
    through the browser. The render worked -- the page grew and
    section.aos-animate appeared, which only exists once Animate-On-Scroll
    initialises in a real browser -- and every layer still found zero rows.
    The listing was not hidden by JavaScript; it is not there. So the
    dependency came back out. 400 MB that provably changes nothing is worse
    than none, and a portal carrying an unnecessary dependency is a portal
    that fails for a reason nobody can act on.
    """
    import inspect

    from jordan_tender_monitor import portals as registry

    # Only a portal backed by a module can reach the browser at all: a
    # data-only portal is a portals.json entry driving the generic cascade,
    # and there is no field in that file which could ask for a render. The
    # dependency is contained by construction for eight of the thirteen.
    coded = {key: module for key, module in registry.MODULES.items()
             if inspect.ismodule(module)}
    check(len(coded) < len(registry.MODULES),
          "browser: most portals are data only and cannot reach it at all",
          f"{len(coded)} of {len(registry.MODULES)} have code")

    users = sorted(key for key, module in coded.items()
                   if "browser." in inspect.getsource(module))
    check_eq(users, ["ungm"],
             "browser: only the portal that demonstrably needs it declares it")
    check(len(users) * 2 < len(registry.MODULES),
          "browser: and it stays a small minority of the thirteen",
          f"{len(users)} of {len(registry.MODULES)}")

    for key in users:
        spec = registry.MODULES[key].SPEC
        check(spec.fetcher is not None,
              f"browser: {key} routes through a custom fetcher")
        check(key in portals.html_portals(),
              f"browser: {key} is still capturable for diagnosis")


# ---------------------------------------------------------------------------
# Degrading when it is absent
# ---------------------------------------------------------------------------

def test_a_missing_browser_is_an_instruction_not_a_traceback():
    """The browser is a diagnostic now, so this is what asks for one.

    Nothing in the report path needs Playwright any more. capture_network()
    still does -- it drives a real page to record what it requests -- so a
    missing browser has to say how to install it rather than traceback.
    """
    original = browser.available
    try:
        browser.available = lambda: False
        try:
            ungm.capture_network()
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


def _endpoint_down(url, payload, **kwargs):
    raise PortalError("HTTP 503 from the search endpoint", url)


def test_ungm_failing_leaves_the_other_portals_alone():
    """One portal's source breaking must not take the run down with it.

    This used to be about an optional dependency; the browser is gone from the
    report path, so it is now about the search endpoint. Same property, and it
    matters more: there is no second path to hide a failure behind, which is
    the point -- a portal that fails loudly beats one that quietly degrades to
    reading a fraction of the wrong list.
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
    original_post = base.post_text
    original_warm = base.warm_session
    try:
        base.warm_session = lambda url: None
        base.post_text = _endpoint_down
        registry.MODULES.clear()
        registry.MODULES.update({"ungm": ungm, "worldbank": _Good})
        config.ENABLED_PORTALS.clear()
        config.ENABLED_PORTALS.update({"ungm": True, "worldbank": True})
        result = scraper.scrape()
    finally:
        base.post_text = original_post
        base.warm_session = original_warm
        registry.MODULES.clear()
        registry.MODULES.update(original_modules)
        config.ENABLED_PORTALS.clear()
        config.ENABLED_PORTALS.update(original_enabled)

    by_key = {h.key: h for h in result.health}
    check_eq(by_key["ungm"].status, "unavailable",
             "ungm: reports unavailable, not a crash")
    check("search endpoint" in by_key["ungm"].reason,
          "ungm: and the reason names the thing that actually broke",
          by_key["ungm"].reason)
    check_eq(by_key["worldbank"].status, "ok",
             "the other portals are unaffected")
    check_eq(len(result.records), 1,
             "and their tenders still reach the report")


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


def test_scrolling_keeps_going_while_rows_keep_arriving():
    """UNGM shows fifteen of thousands and has NO pagination control.

    --capture found nothing but a jQuery datepicker's month arrows and day
    cells, which read as "Prev", "Next", "1", "2", "3". There is no page two to
    follow; the list grows when you scroll it.
    """
    # 15 rows, then 30, 45, 60, then no more.
    page = _FakePage("<html>done</html>", row_counts=[15, 30, 45, 60, 60])
    with _fake_playwright(page=page):
        browser.render("https://www.ungm.org/Public/Notice",
                       settle_ms=0, scroll_for="div.dataRow", max_scrolls=40,
                       scroll_wait_ms=1)
    check_eq(page.scrolls, 4,
             "scroll: it keeps scrolling while the count grows, then stops")
    check_eq(page.locator_selector, "div.dataRow",
             "scroll: rows are counted with the portal's own row selector")


def test_scrolling_asks_the_last_row_to_come_into_view():
    """VERIFIED LIVE: the mouse wheel stalled at 44 rows out of thousands.

    mouse.wheel scrolls whatever is under the cursor, which starts at the
    top-left corner -- the site header, not the listing. UNGM loaded a few
    extra batches and then stopped, which reads exactly like "the list has
    ended" and is not. Asking the last row to scroll itself into view works
    whatever element happens to be the scroll container.
    """
    page = _FakePage("<html>x</html>", row_counts=[15, 30, 45, 45])
    with _fake_playwright(page=page):
        browser.render("https://www.ungm.org/Public/Notice", settle_ms=0,
                       scroll_for="div.dataRow", max_scrolls=10, scroll_wait_ms=1)
    check_eq(page.wheeled, 0,
             "scroll: the mouse wheel is not the mechanism any more")
    check(page.scrolls >= 3, "scroll: the last row was scrolled into view")


def test_scrolling_falls_back_when_a_row_cannot_be_scrolled_to():
    """A detached or hidden row must not end the run.

    The fallback is the old wheel. It is worse, and it is better than losing
    the portal because one element went stale mid-scroll.
    """
    page = _FakePage("<html>x</html>", row_counts=[15, 30, 30])
    page.scroll_into_view_fails = True
    with _fake_playwright(page=page):
        html = browser.render("https://e.org/list", settle_ms=0,
                              scroll_for="div.row", max_scrolls=5,
                              scroll_wait_ms=1)
    check_eq(html, "<html>x</html>", "scroll fallback: the DOM still comes back")
    check(page.wheeled >= 1,
          "scroll fallback: it falls back to the wheel rather than failing")


def test_scrolling_stops_immediately_when_nothing_is_lazy():
    """A page that is not lazily loaded must cost one wait, not forty."""
    page = _FakePage("<html>done</html>", row_counts=[20, 20])
    with _fake_playwright(page=page):
        browser.render("https://e.org/list", settle_ms=0,
                       scroll_for="div.row", max_scrolls=40, scroll_wait_ms=1)
    check_eq(page.scrolls, 1,
             "scroll: one pass proves there is nothing more, and it stops")


def test_scrolling_is_off_unless_a_portal_asks_for_it():
    page = _FakePage("<html>done</html>", row_counts=[10, 20, 30])
    with _fake_playwright(page=page):
        browser.render("https://e.org/list", settle_ms=0)
    check_eq(page.scrolls, 0,
             "scroll: a portal that declares no scroll selector never scrolls")


def test_hitting_the_scroll_cap_is_logged_not_silent():
    """A silent cap makes 'read everything' and 'read the first N' identical.

    This project has already been bitten once by a count that could not
    distinguish an empty portal from a filtered one.
    """
    import logging

    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _Capture()
    log = logging.getLogger("jordan_tender_monitor.portals.browser")
    previous = log.level
    logging.disable(logging.NOTSET)      # the suite disables logging globally
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        # Always growing: the cap is the only thing that can stop it.
        page = _FakePage("<html>x</html>", row_counts=list(range(15, 500, 15)))
        with _fake_playwright(page=page):
            browser.render("https://www.ungm.org/Public/Notice", settle_ms=0,
                           scroll_for="div.dataRow", max_scrolls=3,
                           scroll_wait_ms=1)
        check_eq(page.scrolls, 3, "scroll cap: it stops at the cap")
        warnings = [r for r in records if r.levelno >= logging.WARNING]
        check(warnings, "scroll cap: reaching the cap is reported, not silent")
        if warnings:
            message = warnings[0].getMessage()
            check("cap" in message and "longer than this run read" in message,
                  "scroll cap: and the message says the listing was truncated",
                  f"got {message!r}")
    finally:
        log.removeHandler(handler)
        log.setLevel(previous)
        logging.disable(logging.CRITICAL)


def test_ungm_reads_the_endpoint_directly_with_no_browser_in_the_way():
    """The report path must not touch Playwright at all.

    Kept as an explicit assertion rather than left implicit: a fallback is easy
    to reintroduce by accident, and this one cost ~400 MB and ~30s per run to
    buy a path that only ran once the endpoint was already broken -- and that,
    when it ran, scrolled a WORLDWIDE listing and stopped at a cap.
    """
    check(ungm.SPEC.fetcher is ungm._fetch_search,
          "ungm: fetched straight from the search endpoint")
    check(not hasattr(ungm, "_fetch_rendered"),
          "ungm: the rendered fallback is gone, not merely unused")
    check(ungm.ROW_SELECTOR in ungm.SPEC.selectors,
          "ungm: the row selector used for counting is the one that extracts",
          f"{ungm.ROW_SELECTOR!r} not in {ungm.SPEC.selectors}")


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


def test_ungm_declares_its_source_and_filters_to_jordan():
    check(ungm.SPEC.fetcher is ungm._fetch_search,
          "ungm: the spec uses the search endpoint")
    check_eq(ungm.SPEC.urls, [ungm.LISTING],
             "ungm: the listing page is still the portal's public address")
    check(not ungm.SPEC.filter_to_jordan,
          "ungm: the generic text filter is off; _is_jordan() replaces it "
          "because the country cell cannot express a multi-country notice")
    check("browser" not in ungm.SPEC.notes.lower()
          and "playwright" not in ungm.SPEC.notes.lower(),
          "ungm: the notes no longer advertise a dependency it does not have",
          ungm.SPEC.notes)


# ---------------------------------------------------------------------------
# The environment this actually runs in
# ---------------------------------------------------------------------------

def test_no_ignore_rule_can_swallow_source_it_was_not_aimed_at():
    """A `.gitignore` pattern that hides source is a silent failure.

    `**/data/*` was written to cover jordan_tender_monitor/data/, and it also
    matches ANY directory called data at ANY depth. It swallowed the Android
    app's entire data package -- twelve files, every model and the API client.
    `git add -A` said nothing, the commit looked complete, and the build failed
    with 240 unresolved references pointing at files that were on disk the
    whole time.

    That is the same shape as a scraper returning zero: the output looked like
    a result. So the rules that hide GENERATED state are required to name the
    directory they mean, and any new `**/`-prefixed rule has to be added to the
    allowlist below deliberately, with a reason.
    """
    ignore = (ROOT.parent / ".gitignore").read_text(encoding="utf-8")
    lines = [line.strip() for line in ignore.splitlines()
             if line.strip() and not line.strip().startswith("#")]

    # Patterns that may legitimately match at any depth: they name a file
    # extension or a build artefact, never a source directory.
    allowed_globs = {"**/output/.gitkeep", "**/data/.gitkeep"}

    unscoped = [line for line in lines
                if line.lstrip("!").startswith("**/")
                and line.lstrip("!") not in
                {g.lstrip("!") for g in allowed_globs}]
    check(not unscoped,
          "gitignore: no rule hides a whole directory name at any depth",
          f"unscoped: {unscoped}")

    for directory in ("output", "data"):
        check(f"jordan_tender_monitor/{directory}/*" in lines,
              f"gitignore: the monitor's {directory}/ is ignored by name")

    # And the concrete regression: nothing under android/ may be ignored.
    for path in ("android/app/src/main/java/jo/tendermonitor/data/Outcome.kt",
                 "android/app/src/main/java/jo/tendermonitor/data/db/Database.kt",
                 "android/app/src/test/java/jo/tendermonitor/RedactTest.kt"):
        source = ROOT.parent / path
        check(source.exists(), f"gitignore: {path} is present on disk")
        segments = path.split("/")
        hidden = [line for line in lines
                  if not line.startswith("!")
                  and line.startswith("**/")
                  and line[3:].split("/")[0] in segments]
        check(not hidden,
              f"gitignore: no rule matches a directory in {path}",
              f"would be hidden by {hidden}")


def test_every_workflow_file_is_structurally_valid_yaml():
    """A workflow GitHub cannot parse does not run, and nothing says so.

    There is no red cross for an unparseable workflow: it simply stops being
    scheduled, which is the one failure mode this whole system is built to
    make impossible. It was shipped once already -- an embedded `python -c`
    whose continuation lines started at column 1, which ends the YAML block
    scalar and makes the rest of the file nonsense.

    PyYAML is not a dependency of this project and is not worth becoming one
    for this, so the check is structural rather than a full parse: inside a
    block scalar (`run: |`), every non-blank line must be indented further
    than the key that opened it. That is exactly the mistake that was made,
    and it costs nothing to keep out.
    """
    import re

    workflows = sorted((ROOT.parent / ".github" / "workflows").glob("*.yml"))
    check(len(workflows) >= 2, "workflows: the workflow directory was found",
          f"got {[w.name for w in workflows]}")

    block_re = re.compile(r"^(\s*)[\w-]+:\s*[|>][-+]?\s*$")
    for path in workflows:
        lines = path.read_text(encoding="utf-8").splitlines()
        index = 0
        while index < len(lines):
            match = block_re.match(lines[index])
            if not match:
                index += 1
                continue
            opener_indent = len(match.group(1))
            index += 1
            body = 0
            while index < len(lines):
                line = lines[index]
                if not line.strip():
                    index += 1
                    continue
                indent = len(line) - len(line.lstrip())
                if indent <= opener_indent:
                    break
                body += 1
                index += 1
            check(body > 0,
                  f"workflows: {path.name} has content under every block scalar",
                  f"empty block ending at line {index}")

    # And the specific shape that broke: a bare `from`/`import`/`print` at the
    # start of a line anywhere in a workflow is a continuation that escaped its
    # block. Reported once per file rather than once per line -- a check count
    # that grows with the length of a YAML file measures nothing.
    for path in workflows:
        escaped = [f"line {n}: {line!r}"
                   for n, line in enumerate(path.read_text(encoding="utf-8")
                                            .splitlines(), 1)
                   if re.match(r"^(from|import|print)\b", line)]
        check(not escaped,
              f"workflows: {path.name} has no unindented Python continuation",
              "; ".join(escaped))


def test_the_release_workflow_cannot_silently_skip_a_release():
    """A release that quietly does not happen is the worst kind.

    android.yml has a `paths:` filter so it does not rebuild for a Python-only
    change, and a `paths:` filter applies to TAG pushes too. Putting the tag
    trigger there would skip the release whenever the tagged commit touched
    nothing under android/ -- and nothing would say so. Hence a separate file,
    and this test, which fails if the two are ever merged.
    """
    import io

    workflows = ROOT.parent / ".github" / "workflows"
    build = io.open(workflows / "android.yml", encoding="utf-8").read()
    release = io.open(workflows / "android-release.yml", encoding="utf-8").read()

    def has_key(text: str, key: str) -> bool:
        """A YAML key, not a mention of one.

        Both files TALK about `paths:` in their comments -- explaining exactly
        this trap -- so a substring search finds it in the file that must not
        have it. The distinction is whether the line begins with it.
        """
        return any(line.strip().startswith(key) for line in text.splitlines())

    check(has_key(build, "paths:"),
          "release: the build workflow filters by path, as intended")
    check(not has_key(build, "tags:"),
          "release: and therefore must NOT carry the tag trigger")
    check(has_key(release, "tags:"), "release: the release workflow has it")
    check(not has_key(release, "paths:"),
          "release: and no path filter that could suppress it")

    check("testDebugUnitTest" in release,
          "release: the tests run before anything is published")
    check("gh release create" in release,
          "release: it publishes a real Release, not just an artifact")
    check("sha256sum" in release,
          "release: with a checksum, so a download can be verified")
    check("contents: write" in release,
          "release: and asks for the one permission that needs")

    # `gh release create` refuses when the release exists, and re-cutting a
    # tag by hand is a documented reason to dispatch this workflow. Without a
    # replace path that dispatch fails, leaving the previous APK published
    # under a tag that has moved -- the wrong build, advertised as the right
    # one, which is worse than no release at all.
    check("gh release view" in release,
          "release: it checks whether the release already exists")
    check("--clobber" in release,
          "release: and replaces the asset rather than failing on a re-cut")
    check("gh release edit" in release,
          "release: refreshing the notes too, so they match the new asset")

    # A release can be cut from a branch, and the notes point at ANDROID.md.
    # Pointing at main would 404 for exactly the releases that most need the
    # instructions -- the early ones, cut before the branch merged.
    check("blob/main/" not in release,
          "release: the notes do not link to main, which may not have the file")
    check("/blob/${{ steps.version.outputs.tag }}/android/ANDROID.md" in release,
          "release: they link to the tag, which is the commit that was built")

    check("debug-signed" in release,
          "release: the notes say the APK is debug-signed")
    # Whitespace-normalised: the notes are wrapped prose, and a sentence
    # split across two lines is still the sentence.
    flat = " ".join(release.split())
    check("never been run on a device or an emulator" in flat,
          "release: and repeat that nothing has been run on a device -- a "
          "Releases page is where that stops being obvious")

    # The version has to come from somewhere monotonic, in BOTH workflows, or
    # Android cannot tell one build from another.
    for name, text in (("android.yml", build), ("android-release.yml", release)):
        check("git rev-list --count HEAD" in text,
              f"release: {name} derives a version code from the commit count")
        check("fetch-depth: 0" in text,
              f"release: {name} checks out enough history for it to be right")


def test_the_workflow_installs_the_browser_only_for_diagnosis():
    """The scheduled run must not pay for a browser it does not use.

    ~400 MB and ~30s on every weekday run, for a dependency no portal needs to
    produce the report. It stays installed for --capture, where a real browser
    is the only way to record what a page requests.
    """
    workflow = io.open(ROOT.parent / ".github" / "workflows" / "monitor.yml",
                       encoding="utf-8").read()
    check("requirements-browser.txt" in workflow,
          "workflow: the optional browser requirements are still installable")
    check("playwright install" in workflow,
          "workflow: and chromium itself can still be downloaded")

    install = workflow[workflow.index("requirements-browser.txt") - 800:
                       workflow.index("requirements-browser.txt")]
    check("diagnose portals (--capture)" in install,
          "workflow: the install is gated on diagnosis mode, so a report run "
          "skips it entirely", install[-200:])


def test_the_schedule_is_weekday_mornings_and_not_on_the_hour():
    """A cron that never fires is worse than no cron -- it looks scheduled.

    This workflow ran "0 4 * * 1-5" and had fired ZERO times. GitHub delays or
    drops scheduled runs under load and the top of every hour is the most
    contended minute on the platform; their docs say to pick another one. The
    minute is therefore asserted to be non-zero, not merely present.
    """
    import re
    workflow = io.open(ROOT.parent / ".github" / "workflows" / "monitor.yml",
                       encoding="utf-8").read()
    crons = re.findall(r'cron:\s*"([^"]+)"', workflow)
    check(len(crons) == 1, "workflow: exactly one schedule", repr(crons))

    minute, hour, dom, month, dow = crons[0].split()
    check(minute != "0",
          "workflow: not scheduled on the hour, where GitHub drops crons",
          f"cron is {crons[0]!r}")
    check(0 <= int(hour) <= 6,
          "workflow: early UTC, so it lands in the Amman morning (UTC+3)",
          f"hour={hour}")
    check_eq(dow, "1-5", "workflow: Monday to Friday")
    check_eq((dom, month), ("*", "*"), "workflow: every weekday, every month")


def test_giz_dropped_the_page_that_carried_no_listing():
    """--capture showed giz.de/en/partner/contractor/tenders is an info page.

    Its derived selectors were main-menu__container (74 blocks) and
    main-menu__item (33): pure navigation. Kept in the list it would fail on
    every run and make a working portal look half-broken.
    """
    urls = portals.source_urls("giz")
    check_eq(len(urls), 1, "giz: one source URL, the German portal")
    check("ausschreibungen.giz.de" in urls[0],
          "giz: and it is the ausschreibungen portal")
    check(not any("giz.de/en/partner" in u for u in urls),
          "giz: the English information page is no longer fetched")


TESTS = [
    test_playwright_stays_out_of_the_main_requirements,
    test_importing_the_portals_does_not_import_playwright,
    test_the_browser_dependency_stays_contained,
    test_a_missing_browser_is_an_instruction_not_a_traceback,
    test_render_says_how_to_install_when_the_import_fails,
    test_an_uninstalled_chromium_is_diagnosed_separately_from_a_missing_package,
    test_an_unexpected_render_failure_names_its_exception_type,
    test_ungm_failing_leaves_the_other_portals_alone,
    test_render_returns_the_rendered_dom_and_closes_the_browser,
    test_a_selector_that_never_appears_is_a_hint_not_a_failure,
    test_scrolling_keeps_going_while_rows_keep_arriving,
    test_scrolling_asks_the_last_row_to_come_into_view,
    test_scrolling_falls_back_when_a_row_cannot_be_scrolled_to,
    test_scrolling_stops_immediately_when_nothing_is_lazy,
    test_scrolling_is_off_unless_a_portal_asks_for_it,
    test_hitting_the_scroll_cap_is_logged_not_silent,
    test_ungm_reads_the_endpoint_directly_with_no_browser_in_the_way,
    test_ungm_routes_its_rendered_html_through_the_cascade,
    test_ungm_selectors_come_from_the_rendered_dom,
    test_ungm_declares_its_source_and_filters_to_jordan,
    test_no_ignore_rule_can_swallow_source_it_was_not_aimed_at,
    test_every_workflow_file_is_structurally_valid_yaml,
    test_the_release_workflow_cannot_silently_skip_a_release,
    test_the_workflow_installs_the_browser_only_for_diagnosis,
    test_the_schedule_is_weekday_mornings_and_not_on_the_hour,
    test_giz_dropped_the_page_that_carried_no_listing,
]


# ---------------------------------------------------------------------------
# The search endpoint that replaced the scroll loop
# ---------------------------------------------------------------------------

def _rows(count: int, start: int = 0) -> str:
    """A search-response fragment carrying `count` notice rows."""
    return "".join(
        f'<div class="dataRow notice-table">'
        f'<span class="ungm-title">Notice {start + i}</span>'
        f'<a href="/Public/Notice/{start + i}"></a>'
        f'</div>'
        for i in range(count))


@contextmanager
def _endpoint(pages):
    """Serve `pages` (row counts) from the search endpoint, offline."""
    calls = []
    original_post, original_warm = base.post_text, base.warm_session

    def post_text(url, payload, **kwargs):
        calls.append(payload)
        index = payload["PageIndex"]
        count = pages[index] if index < len(pages) else 0
        return _rows(count, start=index * 100)

    try:
        base.post_text = post_text
        base.warm_session = lambda url: None
        yield calls
    finally:
        base.post_text = original_post
        base.warm_session = original_warm


def test_the_search_body_asks_for_jordan_and_matches_the_captured_shape():
    """Copied from a live network trace, not reconstructed.

    Reconstructing this request is what produced "395 bytes -- the endpoint
    moved or needs a token", which was wrong and cost the portal a headless
    browser and a scroll loop.
    """
    body = ungm._search_body(3, 15)
    check_eq(body["Countries"], [ungm.JORDAN_COUNTRY_ID],
             "ungm: the country filter is what makes the listing small")
    check_eq(ungm.JORDAN_COUNTRY_ID, "2395",
             "ungm: Jordan's id comes from the page's own selNoticeCountry")
    check_eq(body["PageIndex"], 3, "ungm: the page index is what pages")
    for field in ("PageSize", "SortField", "SortAscending", "IsActive",
                  "NoticeSearchTotalLabelId", "TypeOfCompetitions",
                  "UNSPSCs", "NoticeTypes", "Agencies", "isPicker"):
        check(field in body, f"ungm: the captured body's {field!r} is sent too",
              "a field the UI sends and this omits is a difference the server "
              "may act on")


def test_the_endpoint_is_paged_until_a_short_page():
    with _endpoint([15, 15, 7]) as calls:
        html = ungm._fetch_search(ungm.LISTING)
    check_eq([c["PageIndex"] for c in calls], [0, 1, 2],
             "ungm: pages until the listing runs out")
    check_eq(html.count('class="dataRow notice-table"'), 37,
             "ungm: every page's rows survive into one document")


def test_a_capped_page_size_does_not_read_as_the_end_of_the_listing():
    """The trap in measuring the stride wrong.

    If the server caps PageSize at 15 while we ask for 100, EVERY page is
    "short" -- and short-page is the signal for "the listing ended". Assuming
    the requested size would stop after page one and report it as complete,
    which is the silent truncation this whole change exists to remove.
    """
    with _endpoint([15, 15, 15, 4]) as calls:
        html = ungm._fetch_search(ungm.LISTING)
    check_eq(len(calls), 4,
             "ungm: the stride comes from what page one returned, not what was asked")
    check_eq(html.count('class="dataRow notice-table"'), 49,
             "ungm: nothing was dropped by mis-measuring the page size")


def test_one_full_page_then_nothing_terminates():
    """A listing that is an exact multiple of the page size still ends."""
    with _endpoint([15]) as calls:
        ungm._fetch_search(ungm.LISTING)
    check_eq(len(calls), 2,
             "ungm: asks once more, gets nothing, stops")


def test_an_empty_result_is_diagnosed_rather_than_reported_as_no_tenders():
    try:
        with _endpoint([0]):
            ungm._fetch_search(ungm.LISTING)
        check(False, "ungm: an empty search must raise, not return zero rows")
    except PortalError as exc:
        check("--capture ungm" in exc.reason,
              "ungm: and it says which command shows what changed")


def test_a_broken_endpoint_fails_loudly_instead_of_degrading():
    """There is deliberately no second path.

    The browser fallback was dropped because a portal that fails loudly beats
    one that quietly reads a fraction of the wrong list: the fallback scrolled
    UNGM's WORLDWIDE listing and stopped at a cap, so a "successful" fallback
    run would have reported a handful of notices and looked healthy.
    """
    original_available = browser.available
    try:
        # Even WITH a browser available, there is nothing to fall back to.
        browser.available = lambda: True
        with _endpoint([]):
            ungm.fetch_tenders()
        check(False, "ungm: a broken endpoint must raise")
    except PortalError as exc:
        check("search endpoint" in exc.reason,
              "ungm: the reason names what broke", exc.reason)
        check("--capture ungm" in exc.reason,
              "ungm: and the command that shows what it sends now", exc.reason)
        check("playwright" not in exc.reason.lower(),
              "ungm: no browser install hint -- that would send you after the "
              "wrong problem", exc.reason)
    finally:
        browser.available = original_available


TESTS += [
    test_the_search_body_asks_for_jordan_and_matches_the_captured_shape,
    test_the_endpoint_is_paged_until_a_short_page,
    test_a_capped_page_size_does_not_read_as_the_end_of_the_listing,
    test_one_full_page_then_nothing_terminates,
    test_an_empty_result_is_diagnosed_rather_than_reported_as_no_tenders,
    test_a_broken_endpoint_fails_loudly_instead_of_degrading,
]


# ---------------------------------------------------------------------------
# "Multiple destinations" -- the row shape that broke the country filter
# ---------------------------------------------------------------------------

def _ungm_row(title: str, country: str) -> str:
    return (f'<div class="tableRow dataRow notice-table">'
            f'<div class="resultTitle tableCell">'
            f'<span class="ungm-title">{title}</span>'
            f'<a href="/Public/Notice/1" title="Open in a new window"></a></div>'
            f'<span>04-Aug-2026 13:00 (GMT 3.00)</span>'
            f'<span class="remainingDaysToDeadline">0.31</span>'
            f'<span>27-Jul-2026</span><span>UNICEF</span><label>RFQ</label>'
            f'<span>REF-1</span><span>{country}</span></div>')


def _ungm_record(title: str, country: str) -> dict:
    from jordan_tender_monitor.portals import htmlkit
    html = "<html><body>" + _ungm_row(title, country) + "</body></html>"
    rows = htmlkit.extract(html, ungm.LISTING, ["div.dataRow.notice-table"],
                           "/Public/Notice/").rows
    return base.row_to_record("ungm", rows[0])


def test_a_multi_country_notice_is_not_discarded_as_not_jordan():
    """51 of 70 notices were being thrown away, while the count went UP.

    We ask UNGM for Countries=[Jordan] and it answers with 70 rows. Only 19
    print "Jordan" in the country cell; the other 51 print "Multiple
    destinations" -- Jordan notices that also cover other countries, with a
    column too narrow to say so. The generic text filter read that as "not
    Jordan" and dropped three quarters of the portal, and because the endpoint
    change had taken the count from 3 to 19 at the same time, the loss was
    invisible behind an improvement.
    """
    record = _ungm_record("Cash assistance monitoring", "Multiple destinations")
    check(ungm._is_jordan(record),
          "ungm: a multi-destination notice from a Jordan query is kept")


def test_a_row_that_names_jordan_is_kept():
    check(ungm._is_jordan(_ungm_record("Surgical light installation", "Jordan")),
          "ungm: the strongest evidence still works")


def test_a_row_naming_another_country_is_still_dropped():
    """The middle state is a fallback, not an amnesty.

    Where the column CAN express the answer and says something else, believe
    it. Only a column that cannot answer defers to the query.
    """
    check(not ungm._is_jordan(_ungm_record("School rehabilitation", "Mongolia")),
          "ungm: a single-country row that is not Jordan is rejected")


def test_the_scan_count_survives_the_custom_filter():
    """"19 (19 read)" would hide exactly the ratio that exposed this bug."""
    import inspect
    source = inspect.getsource(ungm.fetch_tenders)
    check("note_scanned" in source,
          "ungm: the pre-filter total is still recorded now that harvest() "
          "no longer filters")


TESTS += [
    test_a_multi_country_notice_is_not_discarded_as_not_jordan,
    test_a_row_that_names_jordan_is_kept,
    test_a_row_naming_another_country_is_still_dropped,
    test_the_scan_count_survives_the_custom_filter,
]
