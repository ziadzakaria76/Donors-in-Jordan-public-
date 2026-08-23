"""Offline self-test: the pipeline over committed fixtures.

Runs with a redirected database and output directory so it can never write
fixture ids into real state -- with new-only style reporting, that would make
the next real run look empty and therefore broken.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from .fetch import Fetcher


class FixturePortalMixin:
    """Serve a committed fixture instead of the live page."""

    fixture: Path = None

    def fetch_page(self, label, url):
        return Path(self.fixture).read_text(encoding="utf-8"), 200


def self_test(cfg) -> int:
    from .classify import Classifier
    from .gate import CountryGate
    from .matching import CountryMatcher
    from .pipeline import run as run_pipeline, scope_summary
    from .state import SeenStore

    tmp = Path(tempfile.mkdtemp(prefix="syria-selftest-"))
    matcher = CountryMatcher(cfg.profile)
    CountryGate(cfg.profile, matcher, Classifier(cfg.profile, matcher))
    store = SeenStore(tmp / "selftest.db", read_only=True)   # never the real db

    print(f"Self-test workspace: {tmp}")
    result = run_pipeline(cfg, fetcher=Fetcher(), store=store,
                          today=date.today(), portals=[])
    print(scope_summary(result))
    print("Fixture-driven portal tests live in tests/ and run under pytest;")
    print("this command proves the pipeline wiring holds with no network and no real state.")
    store.close()
    return 0
