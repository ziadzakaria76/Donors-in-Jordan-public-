"""
The portal list, as data.

A portal used to be a Python module. That made the set of portals a code
change, which is fine from a laptop and impossible from a phone -- and adding a
portal is the one piece of configuration that actually changes over time, as
donors move their listings and new ones appear.

So the list lives in `portals.json` and this module turns it into validated
`PortalDef` records. Five portals still need real code (their sources are a
POST search endpoint or a REST API, not a page); they are named in the file by
`module` and their bespoke logic stays where its reasoning is written down. The
rest are data alone, read through the same six-layer extraction cascade every
HTML portal has always used.

THREE RULES THIS FILE EXISTS TO ENFORCE.

**A bad entry names itself and is skipped.** Never a traceback: one malformed
portal must not cost the other twelve their run.

**A skipped entry is never silent.** It comes back as a `problem`, and
`agents/scraper.py` turns every problem into a portal status line reading
`unavailable` with the reason. A portal that vanishes from the report because
of a typo is exactly the failure mode this codebase keeps finding.

**A field the file cannot control is not offered.** An entry with a `module`
declares `code_owned` -- the fields that module sets in code. Setting one of
them in the file is rejected rather than ignored, because a value that is read,
accepted and then overridden is worse than an error: it looks applied.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# The environment override exists for the test suite, which builds registries
# from temporary files. Nothing else should set it.
PORTALS_FILE = Path(os.getenv("JTM_PORTALS_FILE") or BASE_DIR / "portals.json")

# The modules a `module` entry may name. A whitelist, not a dynamic import:
# this file is written by an app over the GitHub API, and "import whatever the
# JSON says" would turn a config write into arbitrary code execution.
CUSTOM_MODULES = ("worldbank", "ted", "samgov", "fcdo", "ungm")

# Portal keys end up in CLI arguments, output filenames and URLs.
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")

SPEC_FIELDS = ("urls", "selectors", "field_selectors", "anchor_hint",
               "currency", "filter_to_jordan")

_ALLOWED_KEYS = {
    "key", "name", "enabled", "tier", "module", "code_owned",
    "no_listing_reason", "notes", *SPEC_FIELDS,
}


@dataclass(frozen=True)
class PortalDef:
    """One portal, as the file declares it."""

    key: str
    name: str
    enabled: bool = True
    tier: int = 2
    # The module that owns this portal's fetch logic, or "" for a portal that
    # is data alone and goes through the generic cascade.
    module: str = ""
    urls: tuple[str, ...] = ()
    selectors: tuple[str, ...] = ()
    field_selectors: dict = field(default_factory=dict)
    anchor_hint: str | None = None
    currency: str | None = None
    filter_to_jordan: bool = True
    # Set for a source that publishes no listing at all. An empty result is
    # then reported as "no listing published" rather than as a broken scraper
    # -- see the ADFD and JICA entries, where this was established the hard way.
    no_listing_reason: str = ""
    # Fields the named module sets in code, which the file therefore must not.
    code_owned: tuple[str, ...] = ()
    notes: str = ""

    @property
    def data_only(self) -> bool:
        return not self.module


@dataclass(frozen=True)
class ConfigProblem:
    """One rejected entry, and why. Reported, never swallowed."""

    key: str
    message: str

    def __str__(self) -> str:
        return f"portals.json: {self.key}: {self.message}"


@dataclass(frozen=True)
class Registry:
    portals: tuple[PortalDef, ...] = ()
    problems: tuple[ConfigProblem, ...] = ()
    # Set when the file itself could not be read or parsed, in which case
    # `portals` is empty and NOTHING can run. Distinct from a list of rejected
    # entries, and handled distinctly: this one has to fail the whole run,
    # because the alternative is a monitor that reports nothing and looks calm.
    fatal: str = ""
    path: str = ""

    def by_key(self, key: str) -> PortalDef | None:
        for portal in self.portals:
            if portal.key == key:
                return portal
        return None

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(p.key for p in self.portals)


# ---------------------------------------------------------------------------
# Validation
#
# Every rejection names the key and says what is wrong with it in words that
# tell you what to change. "invalid entry" is not a diagnosis.
# ---------------------------------------------------------------------------


def _is_str_list(value) -> bool:
    return isinstance(value, list) and all(
        isinstance(v, str) and v.strip() for v in value)


def _validate(entry, index: int, seen: set[str]) -> tuple[PortalDef | None, str]:
    """Return (portal, problem). Exactly one of the two is set."""
    if not isinstance(entry, dict):
        return None, f"entry {index} is a {type(entry).__name__}, not an object"

    key = entry.get("key")
    if not isinstance(key, str) or not KEY_RE.match(key):
        return None, (f"entry {index} has key {key!r}; a key must be lower-case "
                      f"letters, digits, '_' or '-', and start with a letter or "
                      f"digit")
    if key in seen:
        return None, f"'{key}' is defined more than once; the later entry is ignored"

    unknown = sorted(set(entry) - _ALLOWED_KEYS)
    if unknown:
        return None, (f"unknown field(s) {', '.join(unknown)}. Allowed fields: "
                      f"{', '.join(sorted(_ALLOWED_KEYS))}")

    module = entry.get("module", "")
    if module and module not in CUSTOM_MODULES:
        return None, (f"names module {module!r}, which is not one of the modules "
                      f"that exist: {', '.join(CUSTOM_MODULES)}")

    code_owned = entry.get("code_owned", [])
    if not _is_str_list(code_owned) and code_owned != []:
        return None, "code_owned must be a list of field names"
    if code_owned and not module:
        return None, ("declares code_owned but no module, so there is no code "
                      "to own those fields")
    bad_owned = [f for f in code_owned if f not in SPEC_FIELDS]
    if bad_owned:
        return None, (f"code_owned names {', '.join(bad_owned)}, which "
                      f"is not a portal field")
    overridden = [f for f in code_owned if f in entry]
    if overridden:
        return None, (f"sets {', '.join(overridden)}, but portals/{module}.py "
                      f"owns {'that field' if len(overridden) == 1 else 'those fields'} "
                      f"and the file's value would be ignored. Remove it here, "
                      f"or change the module")

    urls = entry.get("urls", [])
    if not _is_str_list(urls) or not urls:
        return None, ("urls must be a non-empty list of http(s) URLs -- a portal "
                      "with no source cannot be read, and would report as broken "
                      "on every run")
    bad_urls = [u for u in urls if not u.lower().startswith(("http://", "https://"))]
    if bad_urls:
        return None, (f"url {bad_urls[0]!r} is not http(s). Only http and https "
                      f"are fetched")

    tier = entry.get("tier", 2)
    if tier not in (1, 2, 3):
        return None, (f"tier is {tier!r}; it must be 1 (API), 2 (HTML) or "
                      f"3 (announcements only)")

    enabled = entry.get("enabled", True)
    if not isinstance(enabled, bool):
        return None, f"enabled is {enabled!r}; it must be true or false"

    selectors = entry.get("selectors", [])
    if not _is_str_list(selectors) and selectors != []:
        return None, "selectors must be a list of CSS selectors"

    field_selectors = entry.get("field_selectors", {})
    if not isinstance(field_selectors, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v.strip()
            for k, v in field_selectors.items()):
        return None, "field_selectors must be an object of field -> CSS selector"

    anchor_hint = entry.get("anchor_hint")
    if anchor_hint is not None and not isinstance(anchor_hint, str):
        return None, "anchor_hint must be a string, or absent"

    currency = entry.get("currency")
    if currency is not None and not (isinstance(currency, str) and currency.strip()):
        return None, "currency must be a currency code, or absent"

    filter_to_jordan = entry.get("filter_to_jordan", True)
    if not isinstance(filter_to_jordan, bool):
        return None, f"filter_to_jordan is {filter_to_jordan!r}; it must be true or false"

    for text_field in ("name", "notes", "no_listing_reason"):
        value = entry.get(text_field, "")
        if not isinstance(value, str):
            return None, f"{text_field} must be a string"

    name = entry.get("name", "").strip() or key
    return PortalDef(
        key=key,
        name=name,
        enabled=enabled,
        tier=tier,
        module=module,
        urls=tuple(urls),
        selectors=tuple(selectors),
        field_selectors=dict(field_selectors),
        anchor_hint=anchor_hint,
        currency=currency,
        filter_to_jordan=filter_to_jordan,
        no_listing_reason=entry.get("no_listing_reason", "").strip(),
        code_owned=tuple(code_owned),
        notes=entry.get("notes", ""),
    ), ""


def load(path: Path | str | None = None) -> Registry:
    """Read and validate the portal file. Never raises."""
    file_path = Path(path) if path else PORTALS_FILE
    try:
        raw = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return Registry(fatal=f"could not be read: {exc.strerror or exc}",
                        path=str(file_path))
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        # The line and column matter: this file is edited from a phone.
        return Registry(
            fatal=f"is not valid JSON: {exc.msg} at line {exc.lineno}, "
                  f"column {exc.colno}",
            path=str(file_path))
    return load_document(document, path=str(file_path))


def load_document(document, path: str = "") -> Registry:
    """Validate an already-parsed portal document.

    Separate from load() so a caller holding the JSON -- the phone app checking
    an edit before it commits it, or a test -- gets exactly the verdict the run
    will get, from the same code. A second validator that agreed most of the
    time would be worse than none.
    """
    if isinstance(document, list):
        entries = document
    elif isinstance(document, dict) and isinstance(document.get("portals"), list):
        entries = document["portals"]
    else:
        return Registry(
            fatal='must be an object with a "portals" array (or a bare array of '
                  'portals)',
            path=path)

    portals: list[PortalDef] = []
    problems: list[ConfigProblem] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        portal, problem = _validate(entry, index, seen)
        if portal is None:
            key = entry.get("key") if isinstance(entry, dict) else None
            problems.append(ConfigProblem(
                key if isinstance(key, str) and key else f"entry {index}", problem))
            continue
        seen.add(portal.key)
        portals.append(portal)

    if not portals:
        return Registry(problems=tuple(problems),
                        fatal="defines no usable portal",
                        path=path)
    return Registry(portals=tuple(portals), problems=tuple(problems),
                    path=path)


REGISTRY = load()


def reload(path: Path | str | None = None) -> Registry:
    """Re-read the file. For tests, and for anything that edits it in place."""
    global REGISTRY
    REGISTRY = load(path)
    return REGISTRY


def get(key: str) -> PortalDef | None:
    return REGISTRY.by_key(key)


def primary_url(key: str) -> str:
    """The first source URL declared for a portal, or "" if it has none.

    Empty is returned rather than raised because the callers are module-level
    constants in the API portals: raising here would turn one bad entry into an
    ImportError and take the whole run down, which is the outcome this file is
    written to prevent. The portals check for it and report it as their reason.
    """
    portal = get(key)
    return portal.urls[0] if portal and portal.urls else ""
