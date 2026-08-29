"""
The portal list as data: portals.json, its loader, and the guarantees it owes.

Three properties are worth more than the rest, and they are the reason this
file exists:

  1. **A portal that is only data really runs.** Key, name and a URL, through
     the same six-layer cascade, into the same records. If that is not true
     then adding a portal from a phone is theatre.

  2. **A malformed entry is named, skipped and REPORTED.** Not a traceback --
     one bad entry must not cost the other twelve their run. And not silence
     either: a portal that vanished from the report because of a typo is the
     worst of the three outcomes, and the one this codebase keeps rediscovering.

  3. **The thirteen existing portals build exactly the specs they built as
     code.** The frozen table below was taken from the modules before they were
     deleted, so this test compares against what actually ran, not against what
     the new file says about itself.
"""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

from jordan_tender_monitor import config, portal_config, portals
from jordan_tender_monitor.portals import base, harvester
from jordan_tender_monitor.portals.base import PortalError

from .harness import check, check_eq

FIXTURES = Path(__file__).resolve().parent / "fixtures"

REAL_FILE = portal_config.PORTALS_FILE


def _serve(name: str):
    html = io.open(FIXTURES / name, encoding="utf-8").read()
    return lambda url: html


class _Registry:
    """Run a block against a portals.json written for the occasion.

    Restores the real registry on the way out, including config's portal
    dictionaries and the built modules -- a test that left a synthetic portal
    behind would make every later test read a portal list nobody wrote.
    """

    def __init__(self, document):
        self.document = document
        self._dir = None

    def __enter__(self) -> portal_config.Registry:
        self._dir = tempfile.TemporaryDirectory(prefix="jtm-portals-")
        path = Path(self._dir.name) / "portals.json"
        if isinstance(self.document, str):
            path.write_text(self.document, encoding="utf-8")
        else:
            path.write_text(json.dumps(self.document), encoding="utf-8")
        self.path = path
        portals.rebuild_from(path)
        return portal_config.REGISTRY

    def __exit__(self, *exc):
        portals.rebuild_from(REAL_FILE)
        self._dir.cleanup()
        return False


def _entry(**overrides) -> dict:
    entry = {"key": "example", "name": "Example Donor", "tier": 2,
             "urls": ["https://example.org/tenders"]}
    entry.update(overrides)
    return entry


def _document(*entries) -> dict:
    return {"version": 1, "portals": list(entries)}


# ---------------------------------------------------------------------------
# 1. A portal that is only data
# ---------------------------------------------------------------------------


def test_a_data_only_portal_round_trips_from_file_to_records():
    """The whole point: a key, a name and a URL, and it reads a listing.

    No module, no class, no registration -- the entry is written to the file
    and the portal exists, goes through the cascade every other HTML portal
    uses, and produces standard records.
    """
    with _Registry(_document(_entry(selectors=[".views-row"]))) as registry:
        check_eq(registry.keys, ("example",),
                 "data portal: the file's entry is the portal list")
        check_eq(config.PORTAL_NAMES.get("example"), "Example Donor",
                 "data portal: its name reaches the report")
        check_eq(config.ENABLED_PORTALS.get("example"), True,
                 "data portal: enabled defaults to true")
        check("example" in portals.html_portals(),
              "data portal: and it is capturable, like every HTML portal")

        module = portals.MODULES["example"]
        check(callable(getattr(module, "fetch_tenders", None)),
              "data portal: exposes the one function every portal must")
        check_eq(portals.source_urls("example"), ["https://example.org/tenders"],
                 "data portal: its URL is the one to check by hand on failure")

        # Through the real cascade, with the network replaced by a fixture.
        module.SPEC.fetcher = _serve("drupal_views.html")
        original = config.FOLLOW_PAGINATION
        try:
            config.FOLLOW_PAGINATION = False
            records = module.fetch_tenders()
        finally:
            config.FOLLOW_PAGINATION = original

        check(records, "data portal: it produces records from a live listing")
        for field_name in base.RECORD_FIELDS:
            check(field_name in records[0],
                  f"data portal: '{field_name}' present, like any other portal")
        check_eq(records[0]["portal"], "example",
                 "data portal: records are tagged with its key")
        check(records[0].get("_layer"),
              "data portal: the winning extraction layer is recorded, so the "
              "first run can say HOW it read the page")


def test_a_data_only_portal_that_reads_nothing_says_which_kind_of_nothing():
    """"0 opportunities" and "could not be read" are different sentences.

    A URL-only portal is best-effort, and the honest thing is to distinguish
    the ways it can come back empty. A blocked host is diagnosed as one; a page
    that loaded and carried no listing is diagnosed as the other.
    """
    with _Registry(_document(_entry())):
        module = portals.MODULES["example"]

        def blocked(url):
            raise PortalError("transport error - ConnectionError (host blocked)", url)

        module.SPEC.fetcher = blocked
        try:
            module.fetch_tenders()
            check(False, "data portal: an unreachable source must raise")
        except PortalError as exc:
            check("transport error" in exc.reason,
                  "data portal: a blocked host is diagnosed as a transport error")
            check_eq(exc.url, "https://example.org/tenders",
                     "data portal: with the URL to check by hand")

        module.SPEC.fetcher = _serve("js_shell.html")
        try:
            module.fetch_tenders()
            check(False, "data portal: a page with no listing must raise")
        except PortalError as exc:
            check("transport error" not in exc.reason,
                  "data portal: a page that LOADED is not reported as unreachable",
                  f"got {exc.reason!r}")
            check("JavaScript shell" in exc.reason,
                  "data portal: a client-rendered page is diagnosed as one, so "
                  "the fix is knowable without opening the site",
                  f"got {exc.reason!r}")

        # And the third case, which is neither: a page that read perfectly and
        # had nothing for Jordan on it. Zero opportunities, no failure.
        module.SPEC.fetcher = _serve("table_listing.html")
        module.SPEC.filter_to_jordan = True
        original = config.FOLLOW_PAGINATION
        try:
            config.FOLLOW_PAGINATION = False
            kept = module.fetch_tenders()
        except PortalError as exc:
            kept = None
            check(False, "data portal: a readable listing must not raise",
                  f"got {exc.reason!r}")
        finally:
            config.FOLLOW_PAGINATION = original
        check(kept is not None and isinstance(kept, list),
              "data portal: a page with no Jordan notices returns a list, not "
              "an error -- '0 opportunities' and 'could not be read' are "
              "different sentences")


def test_disabling_a_portal_stops_it_running_without_deleting_it():
    """The app's on/off switch. Off must mean off, and must be recoverable."""
    with _Registry(_document(_entry(enabled=False),
                             _entry(key="other", name="Other", enabled=True))):
        check("example" in portals.MODULES,
              "disable: the portal is still declared")
        check("example" not in portals.enabled(),
              "disable: but it does not run")
        check("other" in portals.enabled(),
              "disable: and its neighbour is unaffected")


# ---------------------------------------------------------------------------
# 2. A malformed entry
# ---------------------------------------------------------------------------


def _rejected(entry) -> portal_config.ConfigProblem:
    registry = portal_config.load_document(_document(entry), path="<test>")
    return registry.problems[0] if registry.problems else None


def test_a_malformed_entry_names_the_key_and_is_skipped():
    """Never a traceback, never a silent disappearance."""
    document = _document(_entry(key="good", name="Good"),
                         _entry(key="broken", urls=[]),
                         _entry(key="alsogood", name="Also Good"))
    with _Registry(document) as registry:
        check_eq(registry.keys, ("good", "alsogood"),
                 "malformed: the bad entry is skipped and the others survive")
        check_eq(len(registry.problems), 1, "malformed: one problem is reported")
        problem = registry.problems[0]
        check_eq(problem.key, "broken", "malformed: the problem names the key")
        check("urls" in problem.message,
              "malformed: and says which field is wrong", problem.message)
        check(not registry.fatal,
              "malformed: one bad entry is not a fatal file")


def test_every_rejection_says_what_to_change():
    """A diagnosis, not a verdict. "invalid entry" would not be one."""
    cases = [
        (_entry(key="Bad Key"), "key", "a key with spaces and capitals"),
        (_entry(urls="https://example.org"), "urls", "urls given as a string"),
        (_entry(urls=["ftp://example.org/x"]), "http", "a non-http scheme"),
        (_entry(urls=["javascript:alert(1)"]), "http", "a javascript: URL"),
        (_entry(tier=9), "tier", "a tier outside 1-3"),
        (_entry(enabled="yes"), "enabled", "enabled as a string"),
        (_entry(selectors="div.row"), "selectors", "selectors as a string"),
        (_entry(field_selectors={"title": 3}), "field_selectors",
         "a non-string field selector"),
        (_entry(module="nonesuch"), "module", "an unknown module"),
        (_entry(code_owned=["selectors"]), "module", "code_owned with no module"),
        (_entry(colour="blue"), "colour", "a field nobody defined"),
    ]
    for entry, expected, label in cases:
        problem = _rejected(entry)
        if not check(problem is not None, f"rejection: {label} is rejected"):
            continue
        check(expected in problem.message,
              f"rejection: the reason for {label} names '{expected}'",
              problem.message)


def test_a_duplicate_key_is_reported_rather_than_silently_winning():
    """Two entries, one key: which one ran would otherwise be invisible."""
    registry = portal_config.load_document(
        _document(_entry(name="First"), _entry(name="Second")), path="<test>")
    check_eq(len(registry.portals), 1, "duplicate: only one portal is built")
    check_eq(registry.portals[0].name, "First",
             "duplicate: the first entry wins")
    check_eq(len(registry.problems), 1, "duplicate: and the second is reported")
    check("more than once" in registry.problems[0].message,
          "duplicate: the reason says so plainly")


def test_a_rejected_entry_reports_as_unavailable_in_the_status_table():
    """The honesty requirement. A skipped portal must not simply vanish.

    Silence here would be the same failure as a scraper that returns zero: the
    report looks healthy and a source is missing from it.
    """
    from jordan_tender_monitor.agents import scraper

    with _Registry(_document(_entry(key="good", name="Good"),
                             _entry(key="broken", tier=99))):
        health = {h.key: h for h in scraper._config_health()}
        check("broken" in health,
              "rejected entry: it appears in the portal status table")
        entry = health.get("broken")
        if entry:
            check_eq(entry.status, "unavailable",
                     "rejected entry: reported as unavailable")
            check("portals.json" in entry.reason,
                  "rejected entry: the reason names the file to fix")
            check("tier" in entry.reason,
                  "rejected entry: and the field that is wrong", entry.reason)
            check(entry.broken,
                  "rejected entry: it counts as broken, because a portal you "
                  "asked for is not being read")


def test_an_unreadable_file_fails_the_run_rather_than_reporting_nothing():
    """A monitor that reports nothing looks exactly like one that is fine.

    A file-level parse error leaves no portal list at all, so there is nothing
    to attribute a failure to. That is reported as one loud line, and it is
    total: the run goes red, GitHub notifies, and the fix is one commit.
    """
    from jordan_tender_monitor.agents import scraper

    with _Registry('{"portals": [ {"key": "x",  ') as registry:
        check(bool(registry.fatal), "unreadable: the file is marked fatal")
        check("line" in registry.fatal and "column" in registry.fatal,
              "unreadable: with the position, because this is edited on a phone",
              registry.fatal)
        check_eq(registry.portals, (), "unreadable: no portal is invented")

        health = scraper._config_health()
        check(health, "unreadable: the run still reports something")
        check_eq(health[0].status, "unavailable",
                 "unreadable: as an unavailable line, not a clean run")
        check("portal list" in health[0].reason,
              "unreadable: naming the portal list as the cause", health[0].reason)

        result = scraper.ScrapeResult(records=[], health=health)
        check(result.all_broken,
              "unreadable: which makes the run ACTION NEEDED and turns CI red")


def test_a_missing_file_is_diagnosed_not_a_traceback():
    registry = portal_config.load(Path("/nonexistent/portals.json"))
    check(bool(registry.fatal), "missing file: diagnosed")
    check("could not be read" in registry.fatal,
          "missing file: and says so in words", registry.fatal)


def test_a_module_may_not_be_named_by_a_config_write():
    """portals.json is written over the GitHub API by the phone app.

    'import whatever the JSON says' would turn a config write into arbitrary
    code execution, so the modules are a fixed whitelist.
    """
    problem = _rejected(_entry(module="os.system"))
    check(problem is not None, "module whitelist: an arbitrary name is rejected")
    check("worldbank" in problem.message,
          "module whitelist: and the message lists what is allowed")
    for name in portal_config.CUSTOM_MODULES:
        check(portal_config.load_document(
            _document(_entry(module=name, code_owned=[])), path="<t>").portals,
            f"module whitelist: {name} is accepted")


def test_a_field_the_module_owns_is_rejected_rather_than_ignored():
    """A value that is read, accepted and then overridden looks applied.

    UNGM's selectors were derived from the live DOM and are set in the module.
    Accepting them here and ignoring them would be the worst kind of silent
    failure: the file would show what you meant and the run would do something
    else.
    """
    entry = _entry(key="ungm", module="ungm",
                   code_owned=["selectors", "field_selectors", "filter_to_jordan"],
                   selectors=["div.mine"])
    problem = _rejected(entry)
    check(problem is not None, "code_owned: setting an owned field is rejected")
    check("selectors" in problem.message and "portals/ungm.py" in problem.message,
          "code_owned: the reason names the field and the module that owns it",
          problem.message if problem else "")


def test_code_owned_matches_what_the_modules_actually_own():
    """The file's claim about a module has to be true, or it misleads the app.

    The app greys out these fields. If the list drifted from what the module
    overrides, it would either hide an editable field or offer one that does
    nothing.
    """
    for portal in portal_config.REGISTRY.portals:
        if not portal.module:
            check_eq(portal.code_owned, (),
                     f"code_owned: {portal.key} is data only and owns nothing")
            continue
        module = portals._CUSTOM[portal.module]
        declared = getattr(module, "CODE_OWNED", None)
        check(declared is not None,
              f"code_owned: portals/{portal.module}.py declares CODE_OWNED")
        if declared is not None:
            check_eq(set(portal.code_owned), set(declared),
                     f"code_owned: portals.json and portals/{portal.module}.py "
                     f"agree for {portal.key}")


def test_a_portal_with_no_url_is_diagnosed_as_a_config_fault():
    """Not as a site fault: that would send someone to check a working page."""
    spec = harvester.spec_for("nonesuch")
    check_eq(spec.urls, [], "no url: the spec is built rather than raising")
    try:
        harvester.harvest(spec)
        check(False, "no url: harvesting it must raise")
    except PortalError as exc:
        check("portals.json" in exc.reason,
              "no url: and the reason points at the file, not at a site",
              exc.reason)

    try:
        base.require_url("", "nonesuch")
        check(False, "no url: the API portals' guard must raise")
    except PortalError as exc:
        check("portals.json" in exc.reason,
              "no url: the API portals say the same thing")


# ---------------------------------------------------------------------------
# 3. The thirteen, unchanged
# ---------------------------------------------------------------------------

# Taken from the portal MODULES as they stood before the list became data, by
# reading spec.urls / selectors / anchor_hint / currency / filter_to_jordan /
# field_selectors off each one. This is what actually ran, not a restatement of
# the new file -- a test that read portals.json to check portals.json would
# prove nothing.
FROZEN = {
    "worldbank": {"name": "World Bank", "tier": 1, "spec": None,
                  "urls": ["https://search.worldbank.org/api/v2/procnotices"]},
    "ted": {"name": "EU TED", "tier": 1, "spec": None,
            "urls": ["https://api.ted.europa.eu/v3/notices/search"]},
    "samgov": {"name": "SAM.gov (USAID / US Gov)", "tier": 1, "spec": None,
               "urls": ["https://api.sam.gov/prod/opportunities/v2/search"]},
    "fcdo": {"name": "UK Find a Tender", "tier": 1, "spec": None,
             "urls": ["https://www.find-tender.service.gov.uk/api/1.0/"
                      "ocdsReleasePackages"]},
    "ungm": {
        "name": "UNGM (UNDP, UNICEF, WFP, UNOPS, UNHCR, UNRWA)", "tier": 2,
        "urls": ["https://www.ungm.org/Public/Notice"],
        "spec": {
            "selectors": ["div.dataRow.notice-table", "div.tableRow.dataRow",
                          "div.tableRow", "tr.noticeRow"],
            "anchor_hint": "/Public/Notice/", "currency": "USD",
            "filter_to_jordan": False,
            "field_selectors": {
                "title": "span.ungm-title",
                "closing": "span:has(+ span.remainingDaysToDeadline)",
                "posted": "span.remainingDaysToDeadline ~ span"},
            "fetcher": True}},
    "ebrd": {
        "name": "EBRD", "tier": 2,
        "urls": ["https://www.ebrd.com/home/work-with-us/project-procurement/"
                 "procurement-notices.html",
                 "https://ecepp.ebrd.com/delta/noticeSearchResults.html"],
        "spec": {"selectors": ["div.procurement-notice", "article.notice",
                               "li.search-result", "table.noticeTable tbody tr"],
                 "anchor_hint": "/procurement", "currency": "EUR",
                 "filter_to_jordan": True, "field_selectors": {},
                 "fetcher": False}},
    "eib": {
        "name": "EIB", "tier": 2,
        "urls": ["https://www.eib.org/en/about/procurement/all/index.htm"],
        "spec": {"selectors": ["div.eib-list__item", "article.teaser",
                               "li.list-item", "table tbody tr"],
                 "anchor_hint": "/about/procurement/", "currency": "EUR",
                 "filter_to_jordan": True, "field_selectors": {},
                 "fetcher": False}},
    "giz": {
        "name": "GIZ", "tier": 2,
        "urls": ["https://ausschreibungen.giz.de/Satellite/company/welcome.do"],
        "spec": {"selectors": ["div.tender-item", "tr.tableRow",
                               "table.publicationTable tbody tr", "li.result"],
                 "anchor_hint": "/Satellite/notice", "currency": "EUR",
                 "filter_to_jordan": True, "field_selectors": {},
                 "fetcher": False}},
    "kfw": {
        "name": "KfW (via Germany Trade & Invest)", "tier": 2,
        "urls": ["https://www.gtai.de/en/trade/tenders"],
        "spec": {"selectors": ["div.gtai-teaser", "article.teaser",
                               "li.search-result", "table tbody tr"],
                 "anchor_hint": "/tenders/", "currency": "EUR",
                 "filter_to_jordan": True, "field_selectors": {},
                 "fetcher": False}},
    "isdb": {
        "name": "IsDB", "tier": 2,
        "urls": ["https://www.isdb.org/project-procurement/tenders"],
        "spec": {"selectors": ["div.views-row", "div.tender-card",
                               "article.node--type-tender", "table tbody tr"],
                 "anchor_hint": "/project-procurement/", "currency": "USD",
                 "filter_to_jordan": True, "field_selectors": {},
                 "fetcher": False}},
    "sfd": {
        "name": "Saudi Fund for Development", "tier": 3,
        "urls": ["https://www.sfd.gov.sa/en/tenders-view",
                 "https://www.sfd.gov.sa/ar/tenders-view"],
        "spec": {"selectors": ["div.tender-item", "div.card", "table tbody tr",
                               "li.tender"],
                 "anchor_hint": "tender", "currency": "SAR",
                 "filter_to_jordan": True, "field_selectors": {},
                 "fetcher": False}},
    "adfd": {
        "name": "Abu Dhabi Fund for Development", "tier": 3,
        "urls": ["https://www.adfd.ae/en/what-we-do/tenders",
                 "https://www.adfd.ae/en/media-centre/news"],
        "spec": {"selectors": ["div.tender-item", "div.card", "div.news-item",
                               "table tbody tr"],
                 "anchor_hint": None, "currency": "AED",
                 "filter_to_jordan": True, "field_selectors": {},
                 "fetcher": False}},
    "jica": {
        "name": "JICA", "tier": 3,
        "urls": ["https://www.jica.go.jp/english/overseas/jordan/others/"
                 "procurement.html",
                 "https://www.jica.go.jp/jordan/english/office/others/"
                 "procurement.html"],
        "spec": {"selectors": ["div.js-accordion-content li", "ul.list-normal li",
                               "table tbody tr", "div.section li"],
                 "anchor_hint": "procurement", "currency": "JPY",
                 "filter_to_jordan": False, "field_selectors": {},
                 "fetcher": False}},
}


def test_the_thirteen_portals_are_unchanged_by_the_move_to_data():
    """Identical specs to the modules that were deleted, field by field."""
    check_eq(list(portals.MODULES), list(FROZEN),
             "unchanged: the same thirteen portals, in the same order")

    for key, want in FROZEN.items():
        module = portals.MODULES.get(key)
        if not check(module is not None, f"unchanged: {key} still exists"):
            continue
        check_eq(config.PORTAL_NAMES[key], want["name"], f"unchanged: {key} name")
        check_eq(config.PORTAL_TIERS[key], want["tier"], f"unchanged: {key} tier")
        check_eq(config.ENABLED_PORTALS[key], True, f"unchanged: {key} enabled")
        check_eq(portals.source_urls(key), want["urls"], f"unchanged: {key} URLs")

        spec = getattr(module, "SPEC", None)
        if want["spec"] is None:
            check(spec is None,
                  f"unchanged: {key} is an API portal and still has no HtmlSpec")
            continue
        if not check(spec is not None, f"unchanged: {key} still has a spec"):
            continue
        check_eq(list(spec.urls), want["urls"], f"unchanged: {key} spec URLs")
        check_eq(list(spec.selectors), want["spec"]["selectors"],
                 f"unchanged: {key} selectors")
        check_eq(spec.anchor_hint, want["spec"]["anchor_hint"],
                 f"unchanged: {key} anchor hint")
        check_eq(spec.currency, want["spec"]["currency"], f"unchanged: {key} currency")
        check_eq(spec.filter_to_jordan, want["spec"]["filter_to_jordan"],
                 f"unchanged: {key} Jordan filtering")
        check_eq(spec.field_selectors, want["spec"]["field_selectors"],
                 f"unchanged: {key} field selectors")
        check_eq(spec.fetcher is not None, want["spec"]["fetcher"],
                 f"unchanged: {key} custom fetcher")


def test_the_api_portals_read_their_endpoint_from_the_file():
    """So a moved endpoint is a config change, not a release."""
    from jordan_tender_monitor.portals import fcdo, samgov, ted, worldbank

    for module in (worldbank, ted, samgov, fcdo):
        check_eq(module.API, portal_config.primary_url(module.KEY),
                 f"endpoint: {module.KEY} reads its API URL from portals.json")
        check(module.API.startswith("https://"),
              f"endpoint: {module.KEY} has a real endpoint")


def test_ungm_derives_its_search_endpoint_from_the_listing_url():
    """One address, not two the file could set to disagree."""
    from jordan_tender_monitor.portals import ungm

    check_eq(ungm.LISTING, portal_config.primary_url("ungm"),
             "ungm: the listing URL comes from portals.json")
    check_eq(ungm.SEARCH, ungm.LISTING + "/Search",
             "ungm: and the search endpoint is derived from it")


def test_the_file_and_the_module_whitelist_agree():
    check_eq(set(portals._CUSTOM), set(portal_config.CUSTOM_MODULES),
             "whitelist: the resolved modules are exactly the allowed names")
    declared = {p.module for p in portal_config.REGISTRY.portals if p.module}
    check_eq(declared, set(portal_config.CUSTOM_MODULES),
             "whitelist: and every module that exists is used by an entry -- a "
             "module nothing references is dead code nobody would notice")


def test_no_listing_reason_is_data_any_portal_can_declare():
    """It used to be a hand-written wrapper in two modules.

    Two portals need it today. A third -- perhaps one added from the phone --
    might, and the point of moving it into the file is that it can be given one
    without a release.
    """
    reasons = {p.key: p.no_listing_reason
               for p in portal_config.REGISTRY.portals if p.no_listing_reason}
    check_eq(set(reasons), {"adfd", "jica"},
             "no listing: exactly the two sources proven to publish nothing")

    with _Registry(_document(_entry(no_listing_reason="This donor announces "
                                                     "awards only."))):
        module = portals.MODULES["example"]

        def empty(url):
            raise PortalError("HTTP 404 - the URL has moved", url)

        module.SPEC.fetcher = empty
        try:
            module.fetch_tenders()
            check(False, "no listing: an empty portal must still raise")
        except PortalError as exc:
            check(exc.reason.startswith("no listing published"),
                  "no listing: a new portal can be declared quiet, not broken",
                  exc.reason)
            check("404" in exc.reason,
                  "no listing: and the real diagnosis survives after 'Detail:'")


def test_every_portal_in_the_file_is_explained_in_the_prose():
    """PORTALS.md carries the reasoning the file cannot.

    Moving the portals into JSON took the prose out of thirteen modules and put
    it in one document. That only stays true while the document keeps up: a
    portal added to the file and not to the prose leaves the next person
    guessing why it is configured the way it is -- and a portal REMOVED from
    the file but left in the prose is worse, because the explanation reads as
    current.

    Keys are matched, not display names. "IsDB" and "isdb" are not the same
    string, and a check on the display name passes for a portal whose key was
    renamed underneath it.
    """
    import re

    prose = (Path(__file__).resolve().parent.parent / "PORTALS.md").read_text(
        encoding="utf-8")
    headings = re.findall(r"^### .*$", prose, re.M)

    documented = set()
    for heading in headings:
        for key in re.findall(r"`(?:module: )?([a-z0-9_-]+)`", heading):
            documented.add(key)

    in_file = {p.key for p in portal_config.REGISTRY.portals}

    undocumented = sorted(in_file - documented)
    check(not undocumented,
          "prose: every portal in the file has a section in PORTALS.md",
          f"no section for: {undocumented}")

    # `no_listing_reason` is a marker in some headings, not a portal key.
    stale = sorted(documented - in_file - {"no_listing_reason"})
    check(not stale,
          "prose: and PORTALS.md explains no portal the file no longer has",
          f"still documented but gone: {stale}")


TESTS = [
    test_a_data_only_portal_round_trips_from_file_to_records,
    test_a_data_only_portal_that_reads_nothing_says_which_kind_of_nothing,
    test_disabling_a_portal_stops_it_running_without_deleting_it,
    test_a_malformed_entry_names_the_key_and_is_skipped,
    test_every_rejection_says_what_to_change,
    test_a_duplicate_key_is_reported_rather_than_silently_winning,
    test_a_rejected_entry_reports_as_unavailable_in_the_status_table,
    test_an_unreadable_file_fails_the_run_rather_than_reporting_nothing,
    test_a_missing_file_is_diagnosed_not_a_traceback,
    test_a_module_may_not_be_named_by_a_config_write,
    test_a_field_the_module_owns_is_rejected_rather_than_ignored,
    test_code_owned_matches_what_the_modules_actually_own,
    test_a_portal_with_no_url_is_diagnosed_as_a_config_fault,
    test_the_thirteen_portals_are_unchanged_by_the_move_to_data,
    test_the_api_portals_read_their_endpoint_from_the_file,
    test_ungm_derives_its_search_endpoint_from_the_listing_url,
    test_the_file_and_the_module_whitelist_agree,
    test_no_listing_reason_is_data_any_portal_can_declare,
    test_every_portal_in_the_file_is_explained_in_the_prose,
]
