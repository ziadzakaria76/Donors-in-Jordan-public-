"""Portal scrapers. Every module exposes `fetch_tenders() -> list[dict]`."""

from __future__ import annotations

import importlib

# Ordered so the fast, reliable API portals start first in the thread pool.
PORTAL_MODULES = [
    "worldbank",
    "ted",
    "samgov",
    "ungm",
    "fcdo",
    "ebrd",
    "eib",
    "giz",
    "kfw",
    "isdb",
    "sfd",
    "adfd",
    "jica",
]


def load(portal_key: str):
    """Import a portal module by key."""
    return importlib.import_module(f"portals.{portal_key}")
