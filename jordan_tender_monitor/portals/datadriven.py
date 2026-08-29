"""
A portal that is data alone.

Eight of the thirteen portals need no code: a listing URL, some selector hints
and the six-layer cascade are the whole of them. This class is what a
`portals.json` entry with no `module` becomes -- it exposes exactly the
interface the registry requires (`fetch_tenders`, `capture`, `SPEC`), so
nothing downstream can tell the difference between a portal that arrived as
data and one that arrived as a module.

That indistinguishability is the point. A portal added from a phone runs
through the same cascade, the same quality gate and the same failure diagnosis
as EBRD, and shows up in the same status table with the same honesty about
what it managed to read.
"""

from __future__ import annotations

from . import harvester
from .harvester import HtmlSpec


class DataPortal:
    """One portal declared entirely in portals.json."""

    def __init__(self, spec: HtmlSpec):
        self.SPEC = spec
        self.KEY = spec.key

    def fetch_tenders(self) -> list[dict]:
        return harvester.harvest(self.SPEC)

    def capture(self):
        return harvester.capture(self.SPEC)

    def __repr__(self) -> str:  # for test output and log lines
        return f"<DataPortal {self.SPEC.key} urls={len(self.SPEC.urls)}>"


def build(key: str) -> DataPortal:
    """The portal for one data-only key, spec built from portals.json."""
    return DataPortal(harvester.spec_for(key))
