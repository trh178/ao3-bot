"""Decide how to replace a book on the reader without losing her place (DESIGN.md §5).

Pure logic, with no I/O: push.py gathers what the reader says and acts on the plan.

- Mode 1, "in_place": replace the file and write her position back, mapped to
  the new revision.
- Mode 2, "side_by_side": put the new copy next to the old one, seeded with a
  best-guess position. The old copy, and her place in it, stay untouched.

The rule is that an update never costs her place. Anything uncertain goes side
by side.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from .crosspoint import Progress, cache_name

IN_PLACE = "in_place"
SIDE_BY_SIDE = "side_by_side"


@dataclass(frozen=True)
class Placement:
    progress: Progress
    exact: bool   # her chapter was found unchanged (or she'd finished, or was in front matter)
    reason: str


@dataclass(frozen=True)
class CacheState:
    """What the reader has for the copy being replaced."""

    found: bool                        # its /.crosspoint/epub_<hash> folder exists
    progress_bytes: bytes | None = None  # contents of progress.bin, if there is one


@dataclass(frozen=True)
class UpdatePlan:
    mode: str                      # IN_PLACE or SIDE_BY_SIDE
    progress: Progress | None      # what to write for the new copy; None writes nothing
    reason: str


def map_position(old: list[str], new: list[str], pos: Progress) -> Placement | None:
    """Move a position from one revision to the next, using per-item text hashes.

    None means the two revisions share nothing, so there's nothing to go on.
    """
    old_set, new_set = set(old), set(new)
    shared_in_new = [i for i, h in enumerate(new) if h in old_set]
    if not shared_in_new:
        return None

    if pos.spine >= len(old):  # the reader's "end of book"
        start = shared_in_new[-1] + 1
        if start < len(new):
            return Placement(Progress.start_of(start), True, "she'd finished it, so it opens on the first new chapter")
        return Placement(replace(pos, spine=len(new)), True, "she'd finished it, and nothing was added at the end")

    matches = [i for i, h in enumerate(new) if h == old[pos.spine]]
    if matches:
        i = min(matches, key=lambda m: abs(m - pos.spine))
        moved = "" if i == pos.spine else f", now item {i}"
        return Placement(replace(pos, spine=i), True, f"her chapter is unchanged{moved}")

    first_shared_in_old = next(i for i, h in enumerate(old) if h in new_set)
    if pos.spine < first_shared_in_old and pos.spine < len(new):
        return Placement(Progress.start_of(pos.spine), True, "she was in the front matter, which changed")

    guess = min(pos.spine, len(new) - 1)
    return Placement(Progress.start_of(guess), False, "her chapter was rewritten; best guess is its start")


def hash_trusted(recent: list[str], cache_folders: set[str]) -> bool:
    """Can a missing cache folder be taken to mean "never opened"?

    Yes if the cache-folder hash is proven on this reader (a recently opened book's
    folder is where the hash says), or if there are no cache folders at all.
    """
    return not cache_folders or any(cache_name(p) in cache_folders for p in recent)


def plan_update(update_mode: str, cache: CacheState, trusted: bool,
                old_hashes: list[str] | None, new_hashes: list[str] | None) -> UpdatePlan:
    """Choose Mode 1 or Mode 2 for replacing one book. See DESIGN.md §5.4."""
    placement = None
    if cache.progress_bytes is not None:
        pos = Progress.parse(cache.progress_bytes)
        if pos is not None and old_hashes and new_hashes:
            placement = map_position(old_hashes, new_hashes, pos)

    if update_mode == SIDE_BY_SIDE:
        return UpdatePlan(SIDE_BY_SIDE, placement.progress if placement else None, "update_mode is side_by_side")

    if not cache.found:
        if trusted:
            return UpdatePlan(IN_PLACE, None, "never opened, so there's no place to keep")
        return UpdatePlan(SIDE_BY_SIDE, None, "can't find its cache folder, so its place can't be read")

    if cache.progress_bytes is None:
        return UpdatePlan(IN_PLACE, None, "opened, but no saved page yet")
    if Progress.parse(cache.progress_bytes) is None:
        return UpdatePlan(SIDE_BY_SIDE, None, f"progress.bin is {len(cache.progress_bytes)} bytes, not 4, 6 or 10")
    if placement is None:
        return UpdatePlan(SIDE_BY_SIDE, None, "can't compare the two revisions' chapters")
    if placement.exact or update_mode == IN_PLACE:
        return UpdatePlan(IN_PLACE, placement.progress, placement.reason)
    return UpdatePlan(SIDE_BY_SIDE, placement.progress, placement.reason)


@dataclass(frozen=True)
class CopyOnReader:
    """One row of device_files, as cleanup sees it."""

    id: int
    work_id: int
    path: str
    superseded: bool
    opened_at: str | None


def cleanup_due(copies: list[CopyOnReader], present: set[str], recent: list[str],
                now: datetime, grace_days: int, folder: str) -> list[CopyOnReader]:
    """Old side-by-side copies that can go.

    One goes only when:
    - the newest copy of the same work is still on the reader, and
    - she opened that newest copy at least grace_days ago, and
    - the old copy isn't the book she opened most recently, and
    - the old copy is inside the books folder.
    """
    newest: dict[int, CopyOnReader] = {}
    for c in copies:
        if not c.superseded:
            newest[c.work_id] = c
    most_recent = recent[0] if recent else None
    due = []
    for c in copies:
        if not c.superseded or c.path not in present or c.path == most_recent:
            continue
        if not c.path.startswith(folder.rstrip("/") + "/"):
            continue
        current = newest.get(c.work_id)
        if current is None or current.path == c.path or current.path not in present or not current.opened_at:
            continue
        if now - _parse_time(current.opened_at) >= timedelta(days=grace_days):
            due.append(c)
    return due


def _parse_time(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
