"""The source registry.

Adapters register here and the scan runner iterates whatever is enabled. Adding
a source is a matter of appending to this list — the scoring engine never
learns that a new source exists.

Two categories live here:

FETCH sources are scraped or read from an API, and each one must have been
verified against the live site before it is trusted. Until network access is
available in the build environment there are none, and that is stated rather
than papered over with adapters that have never made a request.

DEEP_LINK sources are portals whose terms prohibit automated access. They
generate a pre-filtered search URL the human opens themselves. That is
legitimate, robust against redesigns, and takes about ten seconds.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.base import DeepLinkSource, SourceAdapter

# Every deep-link template below was written from the portal's documented URL
# structure but has NOT yet been opened against the live site, because this
# build environment cannot reach them. Each carries verified=False until it has
# been. An unverified link is shown in the app with that caveat attached rather
# than presented as working.


@dataclass(frozen=True)
class DeepLinkSpec:
    source_id: str
    display_name: str
    template: str
    tos_basis: str
    repair_note: str
    verified: bool = False


DEEP_LINK_SPECS: tuple[DeepLinkSpec, ...] = (
    DeepLinkSpec(
        source_id="bayt",
        display_name="Bayt.com",
        template="https://www.bayt.com/en/saudi-arabia/jobs/{query}-jobs/",
        tos_basis=(
            "Bayt's terms prohibit using any engine, software, tool, agent or "
            "mechanism — spiders, robots, intelligent agents — to navigate or "
            "search the site, other than the search engine and saved searches "
            "Bayt itself provides. Saved searches are explicitly carved out, "
            "which is exactly what this link is."
        ),
        repair_note=(
            "Builds a Bayt keyword search URL for Saudi Arabia. If Bayt changes "
            "its URL structure, open a search on bayt.com by hand and copy the "
            "resulting address into the template. No parsing is involved, so "
            "there is nothing else that can break."
        ),
    ),
    DeepLinkSpec(
        source_id="linkedin",
        display_name="LinkedIn Jobs",
        template=(
            "https://www.linkedin.com/jobs/search/?keywords={query}"
            "&location={location}&f_TPR=r604800"
        ),
        tos_basis=(
            "LinkedIn prohibits automated access outright and enforces it with "
            "account restriction. Scraping it would put Fadi's own account at "
            "risk in a market where his profile is a working asset."
        ),
        repair_note=(
            "Builds a LinkedIn job search URL filtered to the last seven days "
            "(f_TPR=r604800). Nothing is fetched or parsed."
        ),
    ),
)


def deep_link_sources() -> list[DeepLinkSource]:
    return [
        DeepLinkSource(
            source_id=spec.source_id,
            display_name=spec.display_name,
            template=spec.template,
            repair_note=spec.repair_note,
            tos_basis=spec.tos_basis,
        )
        for spec in DEEP_LINK_SPECS
    ]


def fetch_sources() -> list[SourceAdapter]:
    """Sources that are actually scraped.

    Empty until the build environment can reach the internet and each adapter
    has been run against the live site. Returning an empty list is the honest
    answer; a list of never-executed adapters would not be.
    """
    return []


def all_sources() -> list[SourceAdapter]:
    return [*fetch_sources(), *deep_link_sources()]
