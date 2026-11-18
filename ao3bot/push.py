"""Push new and updated EPUBs to the reader (DESIGN.md §4.2).

For now every update goes side by side: the new revision is uploaded next to
the old copy, and the old copy stays where it is. Phase 6 adds in-place
updates and cleanup of old copies.

Rules:
- Only ever upload into the books folder, and never overwrite. A file already
  on the reader under our name is adopted if its size matches (an earlier run
  was cut off after uploading it), and left alone if it doesn't.
- If she deleted a book on the reader, newer revisions of it aren't sent.
- One upload at a time. If the reader goes away, stop; the rest goes next time.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field

from .config import Config
from .names import device_filename
from .reader import FileExists, ReaderClient, ReaderError, ReaderUnavailable, RemoteFile
from .state import now_iso

log = logging.getLogger("ao3bot.push")


@dataclass
class PushResult:
    reachable: bool
    model: str = ""        # "X3" or "X4", from /api/status
    firmware: str = ""
    folder: str = ""       # the books folder, as the reader spells it
    uploaded: list[str] = field(default_factory=list)
    adopted: list[str] = field(default_factory=list)   # already there from a run that was cut off
    skipped: list[str] = field(default_factory=list)   # left alone on purpose, with the reason
    errors: list[str] = field(default_factory=list)
    interrupted: bool = False                          # the reader went away partway through

    @property
    def eventful(self) -> bool:
        return bool(self.uploaded or self.adopted or self.skipped or self.errors or self.interrupted)


@dataclass(frozen=True)
class _Job:
    work_id: int
    rev: int
    title: str
    authors: list[str]
    chapters: int
    update: bool  # True: a newer revision of a work that's already on the reader


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
    try:
        folder = _ensure_folder(client, cfg.device.folder)
        result.folder = folder
        listing = _files(client, folder)
        for job in _plan(conn, cfg.device.name, folder, listing, result):
            listing = _deliver(cfg, conn, client, folder, listing, job, result)
    except ReaderUnavailable as e:
        log.info("reader went away: %s", e)
        result.interrupted = True
    except ReaderError as e:
        result.errors.append(str(e))
    return result


def _ensure_folder(client: ReaderClient, folder: str) -> str:
    """Make sure the books folder exists, and return its path as the reader spells it.

    The SD card ignores case, but the reader keys her position on the exact path
    string, so if the folder already exists as e.g. "/ao3", use that spelling.
    """
    parent, _, name = folder.rpartition("/")
    parent = parent or "/"
    for entry in client.list(parent):
        if entry.name.lower() == name.lower():
            if not entry.is_dir:
                raise ReaderError(f"{folder} on the reader is a file, not a folder")
            if entry.name != name:
                log.warning("the reader already has this folder as %s; using that spelling", entry.name)
            return _join(parent, entry.name)
    client.mkdir(parent, name)
    return folder


def _files(client: ReaderClient, folder: str) -> dict[str, RemoteFile]:
    return {f.name: f for f in client.list(folder) if not f.is_dir}


def _plan(conn: sqlite3.Connection, device: str, folder: str, listing: dict[str, RemoteFile],
          result: PushResult) -> list[_Job]:
    """Work out what to send: each work's newest revision, unless the reader already has it."""
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
            "SELECT rev, path FROM device_files WHERE device = ? AND work_id = ? ORDER BY rev DESC LIMIT 1",
            (device, row["id"]),
        ).fetchone()
        if delivered is not None and delivered["rev"] >= row["rev"]:
            continue  # the reader already has the newest revision (or had it, and she deleted it)
        if delivered is not None and delivered["path"] not in present:
            result.skipped.append(f"{delivered['path']}: deleted on the reader, so newer revisions aren't sent")
            continue
        jobs.append(_Job(
            work_id=row["id"],
            rev=row["rev"],
            title=row["title"],
            authors=json.loads(row["authors"]),
            chapters=row["chapters"],
            update=delivered is not None,
        ))
    return jobs


def _deliver(cfg: Config, conn: sqlite3.Connection, client: ReaderClient, folder: str,
             listing: dict[str, RemoteFile], job: _Job, result: PushResult) -> dict[str, RemoteFile]:
    """Upload one revision and record it. Returns the folder listing as it is afterwards."""
    source = cfg.library_dir / str(job.work_id) / f"rev-{job.rev}.epub"
    try:
        data = source.read_bytes()
    except OSError:
        result.errors.append(f"work {job.work_id} rev {job.rev}: library file missing ({source})")
        return listing

    name = _pick_name(conn, cfg.device.name, job)
    path = _join(folder, name)
    existing = listing.get(name)
    if existing is not None:
        if existing.size == len(data):
            _record(conn, cfg.device.name, job, path)
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
    _record(conn, cfg.device.name, job, path)
    result.uploaded.append(name)
    log.debug("uploaded %s", path)
    return listing


def _pick_name(conn: sqlite3.Connection, device: str, job: _Job) -> str:
    if not job.update:
        return device_filename(job.title, job.authors, job.work_id)
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


def _record(conn: sqlite3.Connection, device: str, job: _Job, path: str) -> None:
    now = now_iso()
    with conn:
        conn.execute(
            "UPDATE device_files SET superseded_at = ? "
            "WHERE device = ? AND work_id = ? AND superseded_at IS NULL",
            (now, device, job.work_id),
        )
        conn.execute(
            "INSERT INTO device_files (device, work_id, rev, path, delivered_at) VALUES (?, ?, ?, ?, ?)",
            (device, job.work_id, job.rev, path, now),
        )


def _join(parent: str, name: str) -> str:
    return f"/{name}" if parent == "/" else f"{parent}/{name}"
