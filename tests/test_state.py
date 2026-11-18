import sqlite3

import pytest

from ao3bot.state import SCHEMA_VERSION, StateError, open_db, row_counts, schema_version


def test_creates_folder_file_and_tables(tmp_path):
    db = tmp_path / "data" / "state.db"
    conn = open_db(db)
    try:
        assert db.is_file()
        assert schema_version(conn) == SCHEMA_VERSION
        assert row_counts(conn) == {"works": 0, "revisions": 0, "device_files": 0}
    finally:
        conn.close()


def test_reopening_is_harmless(tmp_path):
    db = tmp_path / "state.db"
    open_db(db).close()
    conn = open_db(db)
    try:
        assert schema_version(conn) == SCHEMA_VERSION
    finally:
        conn.close()


def test_data_survives_reopening(tmp_path):
    db = tmp_path / "state.db"
    conn = open_db(db)
    with conn:
        conn.execute(
            "INSERT INTO works (id, title, authors, chapters, first_seen) VALUES (?, ?, ?, ?, ?)",
            (123, "A Title", '["An Author"]', "3/?", "2026-11-18T00:00:00Z"),
        )
    conn.close()
    conn = open_db(db)
    try:
        assert row_counts(conn)["works"] == 1
    finally:
        conn.close()


def test_foreign_keys_are_enforced(tmp_path):
    conn = open_db(tmp_path / "state.db")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    "INSERT INTO revisions (work_id, rev, chapters, sha256, chapter_hashes, built_at) "
                    "VALUES (999, 1, 3, 'x', '[]', '2026-11-18T00:00:00Z')"
                )
    finally:
        conn.close()


def test_newer_schema_is_refused(tmp_path):
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.close()
    with pytest.raises(StateError, match="newer|only knows"):
        open_db(db)
