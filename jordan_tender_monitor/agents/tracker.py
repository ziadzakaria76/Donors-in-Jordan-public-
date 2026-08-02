"""
SQLite tracker for already-reported tenders (data/seen_tenders.db).

New-only mode is OFF in the current configuration, so nothing is filtered out by
default. The tracker still records every reported tender, which means you can
switch NEW_ONLY_MODE on (or pass --new-only) at any time and immediately get
new-tenders-only behaviour without a backfill.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing

import config

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_tenders (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    portal        TEXT,
    url           TEXT,
    closing_date  TEXT,
    score         REAL,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seen_portal ON seen_tenders(portal);
"""


def _connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(config.SEEN_DB, timeout=30)
    conn.executescript(SCHEMA)
    return conn


def seen_ids() -> set[str]:
    """IDs already reported in a previous run."""
    try:
        with closing(_connect()) as conn:
            return {row[0] for row in conn.execute("SELECT id FROM seen_tenders")}
    except sqlite3.Error as exc:
        log.warning("Could not read seen-tender database: %s", exc)
        return set()


def record(tenders: list[dict], timestamp: str) -> int:
    """Insert or refresh the tenders included in this run. Returns rows written."""
    if not tenders:
        return 0
    rows = [
        (
            t["id"], t.get("title"), t.get("portal"), t.get("url"),
            t.get("closing_date"), t.get("score"), timestamp, timestamp,
        )
        for t in tenders
    ]
    try:
        with closing(_connect()) as conn:
            conn.executemany(
                """
                INSERT INTO seen_tenders
                    (id, title, portal, url, closing_date, score, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    score     = excluded.score,
                    closing_date = excluded.closing_date
                """,
                rows,
            )
            conn.commit()
        return len(rows)
    except sqlite3.Error as exc:
        log.warning("Could not write seen-tender database: %s", exc)
        return 0


def reset() -> None:
    """Forget every previously reported tender."""
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM seen_tenders")
        conn.commit()
    log.info("seen_tenders database cleared")


def count() -> int:
    try:
        with closing(_connect()) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM seen_tenders").fetchone()[0])
    except sqlite3.Error:
        return 0
