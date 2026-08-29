"""Seen-tender state.

Diagnostics must not mutate production state: a --self-test that runs against
fixtures and writes those fixture ids into the real database makes the next real
run report nothing new, which looks exactly like a broken monitor. Hence
read_only, and MONITOR_DB_PATH so tests can redirect the file entirely.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_tenders (
    key         TEXT PRIMARY KEY,
    portal      TEXT,
    title       TEXT,
    first_seen  TEXT,
    last_seen   TEXT
);
"""


class SeenStore:
    def __init__(self, path: Path, read_only: bool = False):
        self.path = Path(path)
        self.read_only = read_only
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute(SCHEMA)
        self.conn.commit()

    @staticmethod
    def key(portal: str, tender_id: str) -> str:
        return f"{portal}:{tender_id}"

    def known(self, keys: Iterable[str]) -> set[str]:
        keys = list(keys)
        if not keys:
            return set()
        found = set()
        for chunk_start in range(0, len(keys), 400):
            chunk = keys[chunk_start:chunk_start + 400]
            placeholders = ",".join("?" * len(chunk))
            rows = self.conn.execute(
                f"SELECT key FROM seen_tenders WHERE key IN ({placeholders})", chunk)
            found.update(r[0] for r in rows)
        return found

    def record(self, tenders) -> int:
        """No-op when read_only, so diagnostics can never poison the real state."""
        if self.read_only:
            return 0
        today = date.today().isoformat()
        rows = [(self.key(t.portal, t.id), t.portal, t.title, today, today) for t in tenders]
        self.conn.executemany(
            "INSERT INTO seen_tenders (key, portal, title, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET last_seen=excluded.last_seen", rows)
        self.conn.commit()
        return len(rows)

    def mark_new(self, tenders) -> list:
        known = self.known([self.key(t.portal, t.id) for t in tenders])
        for tender in tenders:
            tender.is_new = self.key(tender.portal, tender.id) not in known
        return tenders

    def close(self) -> None:
        self.conn.close()
