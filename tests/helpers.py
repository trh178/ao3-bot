"""Put works and revisions into state.db and the library, the way phase 4 will leave them."""

from __future__ import annotations

import json


def placeholder_epub(work_id: int, rev: int) -> bytes:
    """Bytes that stand in for an EPUB where nothing reads the chapters."""
    return f"fake epub {work_id} rev {rev}\n".encode() * (rev + 1)


def add_work(cfg, conn, work_id, title="A Title", authors=("An Author",), chapters=3, data=None):
    """A work with one built revision (rev 1) and its library file."""
    with conn:
        conn.execute(
            "INSERT INTO works (id, title, authors, chapters, first_seen) VALUES (?, ?, ?, ?, ?)",
            (work_id, title, json.dumps(list(authors)), f"{chapters}/?", "2026-11-18T00:00:00Z"),
        )
    add_revision(cfg, conn, work_id, rev=1, chapters=chapters, data=data)


def add_revision(cfg, conn, work_id, rev, chapters, data=None, hashes=None):
    """Another built revision. `hashes`, if given, is stored as its chapter_hashes."""
    with conn:
        conn.execute(
            "INSERT INTO revisions (work_id, rev, chapters, sha256, chapter_hashes, built_at) "
            "VALUES (?, ?, ?, 'x', ?, '2026-11-18T00:00:00Z')",
            (work_id, rev, chapters, json.dumps(hashes or [])),
        )
    path = cfg.library_dir / str(work_id) / f"rev-{rev}.epub"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if data is not None else placeholder_epub(work_id, rev))
    return path


def rows(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM device_files ORDER BY id")]
