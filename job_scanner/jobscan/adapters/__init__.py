"""Adapter registry.

An adapter's contract: return postings, or raise AdapterError carrying enough
of the real response to diagnose the failure from the Run status sheet alone.
Returning an empty list because something went wrong is forbidden -- a scraper
that returns zero looks exactly like an employer with no vacancies, and the
whole point of the run report is to tell those two apart.
"""

from __future__ import annotations


class AdapterError(Exception):
    """A source could not be read. The message goes into Run status verbatim."""


from .html_table import fetch as _html_table          # noqa: E402
from .json_api import fetch_elevatus as _elevatus      # noqa: E402
from .json_api import fetch_oracle_orc as _oracle_orc  # noqa: E402
from .json_api import fetch_successfactors as _sf      # noqa: E402

ADAPTERS = {
    "html_table": _html_table,
    "successfactors": _sf,
    "oracle_orc": _oracle_orc,
    "elevatus": _elevatus,
}


def get(platform: str):
    adapter = ADAPTERS.get(platform)
    if adapter is None:
        raise AdapterError(
            f"no adapter for platform {platform!r}; known platforms: "
            f"{', '.join(sorted(ADAPTERS))}"
        )
    return adapter
