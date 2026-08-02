"""
Seen-tenders store for new-only mode (Q7).

One rule matters more than the rest: DIAGNOSTICS MUST NOT MUTATE PRODUCTION
STATE. A --self-test that runs on fixtures and records those fixture IDs as
"seen" makes the next real run report nothing, which looks exactly like a
broken monitor. The database path is therefore overridable through
JTM_SEEN_DB, and every diagnostic path opens a temporary one.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from .. import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_tenders (
    id            TEXT PRIMARY KEY,
    portal        TEXT,
    title         TEXT,
    url           TEXT,
    closing_date  TEXT,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seen_portal ON seen_tenders(portal);

CREATE TABLE IF NOT EXISTS run_log (
    run_at        TEXT NOT NULL,
    scanned       INTEGER,
    reported      INTEGER,
    portals_ok    INTEGER,
    portals_total INTEGER
);
"""


class Tracker:
    """Remembers which notices have already been reported."""

    def __init__(self, db_path: Path | str | None = None):
        self.path = Path(db_path or config.SEEN_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # -- queries ------------------------------------------------------------

    def seen_ids(self) -> set[str]:
        with self._connect() as conn:
            return {row[0] for row in conn.execute("SELECT id FROM seen_tenders")}

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM seen_tenders").fetchone()[0]

    def is_first_run(self) -> bool:
        """True when the database is empty.

        The first run after enabling new-only mode reports everything, because
        nothing has been seen yet. That is expected, and the report says so
        rather than leaving you to wonder why the first email is enormous.
        """
        return self.count() == 0

    # -- mutations ----------------------------------------------------------

    def filter_new(self, records: list[dict]) -> list[dict]:
        """Return only records never recorded before. Does not write."""
        if not config.NEW_ONLY_MODE:
            return records
        already = self.seen_ids()
        return [r for r in records if r.get("id") not in already]

    def record(self, records: list[dict]) -> None:
        """Mark records as seen. Called only after a report is delivered."""
        if not records:
            return
        now = datetime.now().isoformat(timespec="seconds")
        rows = [
            (
                r.get("id"),
                r.get("portal"),
                (r.get("title") or "")[:500],
                r.get("url"),
                r["closing_date"].isoformat() if isinstance(r.get("closing_date"), date) else None,
                now,
                now,
            )
            for r in records if r.get("id")
        ]
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO seen_tenders "
                "(id, portal, title, url, closing_date, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen",
                rows,
            )

    def log_run(self, scanned: int, reported: int, portals_ok: int,
                portals_total: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO run_log (run_at, scanned, reported, portals_ok, "
                "portals_total) VALUES (?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), scanned, reported,
                 portals_ok, portals_total),
            )

    def reset(self) -> int:
        """Forget every recorded tender, so the next run reports in full."""
        removed = self.count()
        with self._connect() as conn:
            conn.execute("DELETE FROM seen_tenders")
        return removed
