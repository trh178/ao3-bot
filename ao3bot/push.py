"""Push new and updated EPUBs to the reader (DESIGN.md §4.2 and §5).

- New works are uploaded into the books folder. The pusher never overwrites a
  file it didn't put there.
- Updates follow planner.plan_update: either in place, with her position
  written back (Mode 1), or side by side with a seeded position (Mode 2).
- Old side-by-side copies are deleted once she has opened the new copy and the
  grace period has passed (cleanup_old = "after_switch").
- A book she deleted on the reader is never sent again. A book the reader moved
  to /read when she finished it still gets updates, as a new copy in the books
  folder.
- One upload at a time. If the reader goes away, stop; the rest goes next time.
  An in-place update cut off after its upload landed is finished on the next run,
  from pending_progress.
"""

from __future__ import annotations

import json
import logging
import posixpath
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import Config
from .crosspoint import CACHE_ROOT, READ_FOLDER, RECENT_JSON, Progress, cache_name, recent_paths
from .epub import EpubError, spine_hashes
from .names import device_filename
from .planner import (IN_PLACE, SIDE_BY_SIDE, CacheState, CopyOnReader, cleanup_due, hash_trusted,
                      plan_update)
from .reader import FileExists, ReaderClient, ReaderError, ReaderUnavailable, RemoteFile
from .state import now_iso

log = logging.getLogger("ao3bot.push")


@dataclass
class PushResult:
    reachable: bool
    model: str = ""        # "X3" or "X4", from /api/status
    firmware: str = ""
    folder: str = ""       # the books folder, as the reader spells it
    uploaded: list[str] = field(default_factory=list)   # new works and side-by-side copies
    replaced: list[str] = field(default_factory=list)   # updated in place
    removed: list[str] = field(default_factory=list)    # old copies cleaned up
    adopted: list[str] = field(default_factory=list)    # already there from a run that was cut off
    skipped: list[str] = field(default_factory=list)    # left alone on purpose, with the reason
    notes: list[str] = field(default_factory=list)      # why each update went the way it did
    errors: list[str] = field(default_factory=list)
    interrupted: bool = False                           # the reader went away partway through

    @property
    def eventful(self) -> bool:
        return bool(self.uploaded or self.replaced or self.removed or self.adopted or self.skipped
                    or self.errors or self.interrupted)


@dataclass(frozen=True)
class _Job:
    work_id: int
    rev: int
    title: str
    authors: list[str]
    chapters: int
    old_path: str | None = None   # the copy being updated; None for a new work
    old_rev: int | None = None

    @property
    def update(self) -> bool:
        return self.old_path is not None


class _ReaderView:
    """What the reader says about its own files, fetched lazily, at most once per push."""

    def __init__(self, client: ReaderClient):
        self.client = client
        self._recent: list[str] | None = None
        self._caches: set[str] | None = None
        self._read_folder: dict[str, RemoteFile] | None = None

    @property
    def recent(self) -> list[str]:
        if self._recent is None:
            self._recent = recent_paths(self.client.download(RECENT_JSON))
        return self._recent

    @property
    def cache_folders(self) -> set[str]:
        if self._caches is None:
            self._caches = {f.name for f in self.client.list(CACHE_ROOT) if f.is_dir}
        return self._caches

    @property
    def read_folder(self) -> dict[str, RemoteFile]:
        if self._read_folder is None:
            self._read_folder = _files(self.client, READ_FOLDER)
        return self._read_folder

    def trusted(self) -> bool:
        return hash_trusted(self.recent, self.cache_folders)

    def caches_changed(self) -> None:
        self._caches = None


def push_once(cfg: Config, conn: sqlite3.Connection, client: ReaderClient | None = None) -> PushResult:
    client = client or ReaderClient(cfg.device.host)
    status = client.status()
    if status is None:
        return PushResult(reachable=False)
    result = PushResult(
        reachable=True,
        model=str(status.get("device", "")),
        firmware=str(status.get("version", "")),
    )
    view = _ReaderView(client)
    try:
        folder = _ensure_folder(client, cfg.device.folder)
        result.folder = folder
        _finish_pending(cfg, conn, client, result)
        listing = _files(client, folder)
        for job in _plan(conn, cfg.device.name, folder, listing, view, result):
            listing = _deliver(cfg, conn, client, view, folder, listing, job, result)
        _track_and_clean(cfg, conn, client, view, folder, listing, result)
    except ReaderUnavailable as e:
        log.info("reader went away: %s", e)
        result.interrupted = True
    except ReaderError as e:
        result.errors.append(str(e))
    return result


# -- what to send ----------------------------------------------------------------

def _ensure_folder(client: ReaderClient, folder: str) -> str:
    """Make sure the books folder exists, and return its path as the reader spells it.

    The SD card ignores case, but the reader keys her position on the exact path
    string, so if the folder already exists as e.g. "/ao3", use that spelling.
    """
    parent, name = _split(folder)
    for entry in client.list(parent):
        if entry.name.lower() == name.lower():
            if not entry.is_dir:
                raise ReaderError(f"{folder} on the reader is a file, not a folder")
            if entry.name != name:
                log.warning("the reader already has this folder as %s; using that spelling", entry.name)
            return _join(parent, entry.name)
    client.mkdir(parent, name)
    return folder


def _plan(conn: sqlite3.Connection, device: str, folder: str, listing: dict[str, RemoteFile],
          view: _ReaderView, result: PushResult) -> list[_Job]:
    """Each work's newest revision, unless the reader already has it."""
    present = {_join(folder, name) for name in listing}
    latest = conn.execute(
        """
        SELECT w.id, w.title, w.authors, r.rev, r.chapters
        FROM works w JOIN revisions r ON r.work_id = w.id
        WHERE r.rev = (SELECT MAX(rev) FROM revisions WHERE work_id = w.id)
        ORDER BY w.first_seen, w.id
        """
    ).fetchall()
    jobs = []
    for row in latest:
        delivered = conn.execute(
            "SELECT rev, path FROM device_files WHERE device = ? AND work_id = ? ORDER BY rev DESC, id DESC LIMIT 1",
            (device, row["id"]),
        ).fetchone()
        if delivered is not None and delivered["rev"] >= row["rev"]:
            continue  # the reader has the newest revision (or had it, and she deleted it)
        old_path = None
        if delivered is not None:
            old_path = delivered["path"]
            if old_path not in present:
                old_path = _moved_to_read(view, old_path)
                if old_path is None:
                    result.skipped.append(
                        f"{delivered['path']}: deleted on the reader, so newer revisions aren't sent")
                    continue
        jobs.append(_Job(
            work_id=row["id"],
            rev=row["rev"],
            title=row["title"],
            authors=json.loads(row["authors"]),
            chapters=row["chapters"],
            old_path=old_path,
            old_rev=delivered["rev"] if delivered is not None else None,
        ))
    return jobs


def _moved_to_read(view: _ReaderView, path: str) -> str | None:
    """Where the reader moved a finished book, if it did: /read/<name> or /read/<name> (N).epub."""
    _, name = _split(path)
    stem, ext = posixpath.splitext(name)
    names = view.read_folder
    for candidate in [name] + [f"{stem} ({n}){ext}" for n in range(2, 100)]:
        if candidate in names:
            return _join(READ_FOLDER, candidate)
    return None


# -- sending -------------------------------------------------------------------

def _deliver(cfg: Config, conn: sqlite3.Connection, client: ReaderClient, view: _ReaderView, folder: str,
             listing: dict[str, RemoteFile], job: _Job, result: PushResult) -> dict[str, RemoteFile]:
    """Send one revision and record it. Returns the books folder's listing as it is afterwards."""
    source = cfg.library_dir / str(job.work_id) / f"rev-{job.rev}.epub"
    try:
        data = source.read_bytes()
    except OSError:
        result.errors.append(f"work {job.work_id} rev {job.rev}: library file missing ({source})")
        return listing

    if not job.update:
        name = device_filename(job.title, job.authors, job.work_id)
        return _upload_copy(cfg, conn, client, view, folder, listing, job, data, name, None, result)

    old_folder, old_name = _split(job.old_path)
    moved = old_folder != folder
    cache = _cache_state(client, view, job.old_path)
    old_hashes = new_hashes = None
    if cache.progress_bytes is not None:
        old_hashes = _stored_hashes(cfg, conn, job.work_id, job.old_rev)
        new_hashes = _hashes(data)
    mode = SIDE_BY_SIDE if moved else cfg.device.update_mode
    plan = plan_update(mode, cache, view.trusted(), old_hashes, new_hashes)
    why = f"moved to {READ_FOLDER} when she finished it; {plan.reason}" if moved else plan.reason
    result.notes.append(f"{old_name}: {why}")

    if plan.mode == IN_PLACE:
        return _replace_in_place(cfg, conn, client, view, folder, listing, job, data, plan.progress, result)
    name = _side_by_side_name(conn, cfg.device.name, job)
    return _upload_copy(cfg, conn, client, view, folder, listing, job, data, name, plan.progress, result)


def _upload_copy(cfg: Config, conn: sqlite3.Connection, client: ReaderClient, view: _ReaderView, folder: str,
                 listing: dict[str, RemoteFile], job: _Job, data: bytes, name: str, seed: Progress | None,
                 result: PushResult) -> dict[str, RemoteFile]:
    """Upload a new file (a new work, or a side-by-side copy) without overwriting anything."""
    path = _join(folder, name)
    existing = listing.get(name)
    if existing is not None:
        if existing.size == len(data):
            _record(conn, cfg.device.name, job.work_id, job.rev, path)
            result.adopted.append(name)
        else:
            result.skipped.append(f"{name}: a different file with this name is already on the reader; left alone")
        return listing

    try:
        client.upload(folder, name, data)
    except FileExists:
        result.skipped.append(f"{name}: appeared on the reader during the push; checking again next time")
        return _files(client, folder)
    except ReaderError as e:
        result.errors.append(str(e))
        return listing

    listing = _files(client, folder)
    landed = listing.get(name)
    if landed is None or landed.size != len(data):
        result.errors.append(f"{name}: uploaded, but the reader doesn't list it with the right size")
        return listing
    if seed is not None:
        try:
            _write_progress(client, path, seed.to_bytes())
            view.caches_changed()
        except ReaderError as e:
            result.errors.append(f"{name}: uploaded, but its starting position wasn't saved ({e})")
    _record(conn, cfg.device.name, job.work_id, job.rev, path)
    result.uploaded.append(name)
    log.debug("uploaded %s", path)
    return listing


def _replace_in_place(cfg: Config, conn: sqlite3.Connection, client: ReaderClient, view: _ReaderView,
                      folder: str, listing: dict[str, RemoteFile], job: _Job, data: bytes,
                      progress: Progress | None, result: PushResult) -> dict[str, RemoteFile]:
    """Mode 1: overwrite the file (which wipes its cache), then write her position back."""
    device = cfg.device.name
    parent, name = _split(job.old_path)
    if progress is not None:
        with conn:  # if the reader goes away after the upload lands, the next run finishes this
            conn.execute(
                "INSERT OR REPLACE INTO pending_progress (device, path, work_id, rev, size, progress, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (device, job.old_path, job.work_id, job.rev, len(data), progress.to_bytes(), now_iso()),
            )
    try:
        client.upload(parent, name, data, overwrite=True)
    except ReaderError as e:
        _drop_pending(conn, device, job.old_path)
        result.errors.append(str(e))
        return listing
    view.caches_changed()

    landed = _files(client, parent).get(name)
    if landed is None or landed.size != len(data):
        result.errors.append(f"{name}: replaced, but the reader doesn't list it with the right size")
        return _files(client, folder)
    if progress is not None:
        try:
            _write_progress(client, job.old_path, progress.to_bytes())
        except ReaderError as e:
            result.errors.append(f"{name}: replaced, but her position wasn't written back yet ({e}); retrying next time")
            return _files(client, folder)
        _drop_pending(conn, device, job.old_path)
    _record(conn, device, job.work_id, job.rev, job.old_path, replaced=True)
    result.replaced.append(name)
    return _files(client, folder)


def _finish_pending(cfg: Config, conn: sqlite3.Connection, client: ReaderClient, result: PushResult) -> None:
    """Finish in-place updates that were cut off after the upload, before her position was written."""
    device = cfg.device.name
    for row in conn.execute("SELECT * FROM pending_progress WHERE device = ?", (device,)).fetchall():
        parent, name = _split(row["path"])
        landed = _files(client, parent).get(name)
        if landed is not None and landed.size == row["size"]:
            # Only if she hasn't opened it since: a newer saved page is hers to keep.
            if client.download(f"{CACHE_ROOT}/{cache_name(row['path'])}/progress.bin") is None:
                _write_progress(client, row["path"], bytes(row["progress"]))
            _record(conn, device, row["work_id"], row["rev"], row["path"], replaced=True)
            result.replaced.append(f"{name} (finished an update that was cut off)")
        _drop_pending(conn, device, row["path"])  # if the upload never landed, nothing was lost


def _write_progress(client: ReaderClient, book_path: str, data: bytes) -> None:
    """Write progress.bin for a book into its cache folder, and read it back."""
    name = cache_name(book_path)
    client.mkdir("/", CACHE_ROOT.lstrip("/"))
    client.mkdir(CACHE_ROOT, name)
    cache = f"{CACHE_ROOT}/{name}"
    client.upload(cache, "progress.bin", data, overwrite=True, content_type="application/octet-stream")
    if client.download(f"{cache}/progress.bin") != data:
        raise ReaderError(f"progress.bin for {book_path} didn't read back the same")


def _cache_state(client: ReaderClient, view: _ReaderView, book_path: str) -> CacheState:
    name = cache_name(book_path)
    if name not in view.cache_folders:
        return CacheState(found=False)
    return CacheState(found=True, progress_bytes=client.download(f"{CACHE_ROOT}/{name}/progress.bin"))


def _stored_hashes(cfg: Config, conn: sqlite3.Connection, work_id: int, rev: int | None) -> list[str] | None:
    """Chapter hashes of a delivered revision: from state.db, or else from its library file."""
    row = conn.execute(
        "SELECT chapter_hashes FROM revisions WHERE work_id = ? AND rev = ?", (work_id, rev)
    ).fetchone()
    if row is not None:
        stored = json.loads(row["chapter_hashes"] or "[]")
        if stored:
            return stored
    path = cfg.library_dir / str(work_id) / f"rev-{rev}.epub"
    return _hashes(path.read_bytes()) if path.is_file() else None


def _hashes(data: bytes) -> list[str] | None:
    try:
        return spine_hashes(data)
    except EpubError as e:
        log.warning("can't read chapters: %s", e)
        return None


def _side_by_side_name(conn: sqlite3.Connection, device: str, job: _Job) -> str:
    taken = {
        row["path"].rsplit("/", 1)[-1]
        for row in conn.execute(
            "SELECT path FROM device_files WHERE device = ? AND work_id = ?", (device, job.work_id)
        )
    }
    name = device_filename(job.title, job.authors, job.work_id, tag=f"ch {job.chapters}")
    if name in taken:  # an edit that kept the chapter count
        name = device_filename(job.title, job.authors, job.work_id, tag=f"ch {job.chapters}, rev {job.rev}")
    return name


# -- after sending ---------------------------------------------------------------

def _track_and_clean(cfg: Config, conn: sqlite3.Connection, client: ReaderClient, view: _ReaderView,
                     folder: str, listing: dict[str, RemoteFile], result: PushResult) -> None:
    """Note which copies she has opened, then delete old side-by-side copies that are due."""
    device = cfg.device.name
    now = now_iso()
    present = {_join(folder, name) for name in listing}
    recent = view.recent
    with conn:
        for path in recent:
            conn.execute(
                "UPDATE device_files SET opened_at = ? "
                "WHERE device = ? AND path = ? AND opened_at IS NULL AND removed_at IS NULL",
                (now, device, path),
            )
        for row in conn.execute(
            "SELECT id, path FROM device_files WHERE device = ? AND superseded_at IS NOT NULL AND removed_at IS NULL",
            (device,),
        ).fetchall():
            if _split(row["path"])[0] == folder and row["path"] not in present:
                conn.execute("UPDATE device_files SET removed_at = ? WHERE id = ?", (now, row["id"]))  # she deleted it

    if cfg.device.cleanup_old != "after_switch":
        return
    copies = [
        CopyOnReader(id=r["id"], work_id=r["work_id"], path=r["path"],
                     superseded=r["superseded_at"] is not None, opened_at=r["opened_at"])
        for r in conn.execute(
            "SELECT id, work_id, path, superseded_at, opened_at FROM device_files "
            "WHERE device = ? AND removed_at IS NULL ORDER BY id",
            (device,),
        )
    ]
    due = cleanup_due(copies, present, recent, datetime.now(timezone.utc), cfg.device.cleanup_grace_days, folder)
    for copy in due:
        try:
            client.delete(copy.path)
        except ReaderError as e:
            result.errors.append(str(e))
            continue
        with conn:
            conn.execute("UPDATE device_files SET removed_at = ? WHERE id = ?", (now_iso(), copy.id))
        result.removed.append(_split(copy.path)[1])


# -- state.db --------------------------------------------------------------------

def _record(conn: sqlite3.Connection, device: str, work_id: int, rev: int, path: str,
            replaced: bool = False) -> None:
    """Record a delivered revision. Earlier copies of the work become superseded."""
    now = now_iso()
    with conn:
        if replaced:
            conn.execute(
                "UPDATE device_files SET removed_at = ? "
                "WHERE device = ? AND work_id = ? AND path = ? AND removed_at IS NULL",
                (now, device, work_id, path),
            )
        conn.execute(
            "UPDATE device_files SET superseded_at = ? "
            "WHERE device = ? AND work_id = ? AND superseded_at IS NULL",
            (now, device, work_id),
        )
        conn.execute(
            "INSERT INTO device_files (device, work_id, rev, path, delivered_at) VALUES (?, ?, ?, ?, ?)",
            (device, work_id, rev, path, now),
        )


def _drop_pending(conn: sqlite3.Connection, device: str, path: str) -> None:
    with conn:
        conn.execute("DELETE FROM pending_progress WHERE device = ? AND path = ?", (device, path))


def _files(client: ReaderClient, folder: str) -> dict[str, RemoteFile]:
    return {f.name: f for f in client.list(folder) if not f.is_dir}


def _split(path: str) -> tuple[str, str]:
    parent, _, name = path.rpartition("/")
    return parent or "/", name


def _join(parent: str, name: str) -> str:
    return f"/{name}" if parent == "/" else f"{parent}/{name}"
