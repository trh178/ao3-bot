"""state.db: works, their built revisions, and what's on each reader.

The schema version lives in PRAGMA user_version. To change the schema, add a
new entry to MIGRATIONS. Never edit an entry that has already run on the Pi.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS: list[str] = [
    # v1: the three tables from DESIGN.md §2
    """
    CREATE TABLE works (
        id            INTEGER PRIMARY KEY,          -- the AO3 work ID
        title         TEXT NOT NULL,
        authors       TEXT NOT NULL,                -- JSON list of names
        chapters      TEXT NOT NULL,                -- as AO3 shows it, e.g. "14/?" or "20/20"
        complete      INTEGER NOT NULL DEFAULT 0,
        ao3_updated   TEXT,                         -- AO3's "updated" date, YYYY-MM-DD
        sources       TEXT NOT NULL DEFAULT '[]',   -- JSON list, e.g. ["marked_for_later"]
        first_seen    TEXT NOT NULL,                -- ISO 8601, UTC
        last_checked  TEXT                          -- ISO 8601, UTC
    );

    CREATE TABLE revisions (
        work_id         INTEGER NOT NULL REFERENCES works(id),
        rev             INTEGER NOT NULL,
        chapters        INTEGER NOT NULL,
        sha256          TEXT NOT NULL,              -- of the whole EPUB file
        chapter_hashes  TEXT NOT NULL,              -- JSON list of per-chapter text hashes (phase 4)
        built_at        TEXT NOT NULL,              -- ISO 8601, UTC
        PRIMARY KEY (work_id, rev)
    );

    CREATE TABLE device_files (
        id             INTEGER PRIMARY KEY,
        device         TEXT NOT NULL,               -- [device] name from config
        work_id        INTEGER NOT NULL,
        rev            INTEGER NOT NULL,
        path           TEXT NOT NULL,               -- the exact path on the reader
        delivered_at   TEXT NOT NULL,               -- ISO 8601, UTC
        superseded_at  TEXT,                        -- set when a newer revision replaces it
        FOREIGN KEY (work_id, rev) REFERENCES revisions(work_id, rev)
    );

    CREATE INDEX device_files_by_work ON device_files(device, work_id);
    """,
]

SCHEMA_VERSION = len(MIGRATIONS)
TABLES = ("works", "revisions", "device_files")


class StateError(Exception):
    """state.db can't be used as it is."""


def open_db(path: Path) -> sqlite3.Connection:
    """Open state.db, creating its folder, the file and the tables if they're missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        migrate(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> int:
    """Bring the schema up to SCHEMA_VERSION. Each step runs in its own transaction."""
    current = schema_version(conn)
    if current > SCHEMA_VERSION:
        raise StateError(
            f"state.db is schema v{current}, but this code only knows up to v{SCHEMA_VERSION}; "
            "update the code rather than the database"
        )
    for version in range(current + 1, SCHEMA_VERSION + 1):
        script = MIGRATIONS[version - 1]
        try:
            conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {version};\nCOMMIT;")
        except sqlite3.Error:
            conn.rollback()
            raise
    return schema_version(conn)


def now_iso() -> str:
    """The current time in UTC, as stored in state.db: "2026-11-18T13:40:00Z"."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in TABLES}
