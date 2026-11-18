from datetime import datetime, timezone

import pytest

from ao3bot.crosspoint import Progress, cache_name
from ao3bot.epub import spine_hashes
from ao3bot.planner import (IN_PLACE, SIDE_BY_SIDE, CacheState, CopyOnReader, cleanup_due, hash_trusted,
                            map_position, plan_update)

from .epubs import SAMPLES, insert_item, rewrite_item, truncate_spine

needs_samples = pytest.mark.skipif(not SAMPLES, reason="no sample EPUBs in the project root")

OLD = ["title-v1", "a", "b", "c"]
APPENDED = ["title-v2", "a", "b", "c", "d"]
REWRITTEN = ["title-v2", "a", "B!", "c"]
HERE = Progress(2, 5, 9, 1234)  # in chapter "b", page 5 of 9


# -- map_position ------------------------------------------------------------

def test_appended_chapters_keep_her_exact_spot():
    p = map_position(OLD, APPENDED, HERE)
    assert p.exact and p.progress == HERE


def test_an_inserted_chapter_moves_her_index():
    p = map_position(OLD, ["title-v2", "a", "new", "b", "c"], HERE)
    assert p.exact and p.progress == Progress(3, 5, 9, 1234)


def test_a_rewritten_chapter_is_a_best_guess():
    p = map_position(OLD, REWRITTEN, HERE)
    assert not p.exact and p.progress == Progress.start_of(2)


def test_finished_opens_on_the_first_new_chapter():
    p = map_position(OLD, APPENDED, Progress(4, 0, 0))  # spine == len(OLD): the reader's end of book
    assert p.exact and p.progress == Progress.start_of(4)


def test_finished_with_nothing_new_stays_finished():
    p = map_position(OLD, ["title-v2", "a", "b", "c"], Progress(4, 0, 0))
    assert p.exact and p.progress.spine == 4


def test_front_matter_that_changed():
    p = map_position(OLD, APPENDED, Progress(0, 1, 2))
    assert p.exact and p.progress == Progress.start_of(0)


def test_nothing_in_common():
    assert map_position(OLD, ["x", "y"], Progress(1, 0)) is None


def test_duplicate_items_pick_the_nearest():
    old = ["t", "sep", "a", "sep", "b"]
    new = ["t2", "sep", "a", "sep", "b", "sep", "c"]
    assert map_position(old, new, Progress(3, 0, 1)).progress.spine == 3


# -- plan_update -------------------------------------------------------------

def plan(mode="auto", found=True, progress=HERE, trusted=True, old=OLD, new=APPENDED):
    raw = progress.to_bytes() if isinstance(progress, Progress) else progress
    return plan_update(mode, CacheState(found, raw), trusted, old, new)


def test_exact_goes_in_place():
    p = plan()
    assert p.mode == IN_PLACE and p.progress == HERE


def test_rewritten_goes_side_by_side_with_a_best_guess():
    p = plan(new=REWRITTEN)
    assert p.mode == SIDE_BY_SIDE and p.progress == Progress.start_of(2)


def test_in_place_mode_accepts_a_best_guess():
    p = plan(mode="in_place", new=REWRITTEN)
    assert p.mode == IN_PLACE and p.progress == Progress.start_of(2)


def test_side_by_side_mode_always_and_still_seeds():
    p = plan(mode="side_by_side")
    assert p.mode == SIDE_BY_SIDE and p.progress == HERE


def test_never_opened_with_a_proven_hash():
    p = plan(found=False, progress=None)
    assert p.mode == IN_PLACE and p.progress is None


def test_missing_cache_folder_with_an_unproven_hash():
    p = plan(found=False, progress=None, trusted=False)
    assert p.mode == SIDE_BY_SIDE and p.progress is None


def test_in_place_mode_still_wont_go_blind():
    assert plan(mode="in_place", found=False, progress=None, trusted=False).mode == SIDE_BY_SIDE


def test_opened_without_a_saved_page():
    p = plan(progress=None)
    assert p.mode == IN_PLACE and p.progress is None


def test_an_odd_progress_file():
    p = plan(progress=b"\x00" * 7)
    assert p.mode == SIDE_BY_SIDE and p.progress is None


def test_revisions_that_cant_be_read():
    p = plan(old=None)
    assert p.mode == SIDE_BY_SIDE and p.progress is None


# -- hash_trusted ------------------------------------------------------------

def test_trusted_when_a_recent_book_has_its_folder():
    assert hash_trusted(["/AO3/a.epub"], {cache_name("/AO3/a.epub"), "epub_1"})


def test_not_trusted_when_recent_books_have_no_folders():
    assert not hash_trusted(["/AO3/a.epub"], {"epub_1"})


def test_trusted_when_nothing_was_ever_opened():
    assert hash_trusted([], set())


def test_not_trusted_with_folders_but_no_recent_books():
    assert not hash_trusted([], {"epub_1"})


# -- cleanup_due -------------------------------------------------------------

NOW = datetime(2026, 12, 20, tzinfo=timezone.utc)
PRESENT = {"/AO3/old.epub", "/AO3/new.epub"}


def copies(opened="2026-12-01T00:00:00Z", old_path="/AO3/old.epub"):
    return [CopyOnReader(1, 7, old_path, True, "2026-11-20T00:00:00Z"),
            CopyOnReader(2, 7, "/AO3/new.epub", False, opened)]


def due(cs=None, present=PRESENT, recent=("/AO3/new.epub",), grace=7):
    return [c.path for c in cleanup_due(cs or copies(), set(present), list(recent), NOW, grace, "/AO3")]


def test_the_old_copy_goes_after_the_grace_period():
    assert due() == ["/AO3/old.epub"]


def test_not_before_the_grace_period():
    assert due(copies(opened="2026-12-18T00:00:00Z")) == []


def test_not_until_she_opens_the_new_copy():
    assert due(copies(opened=None)) == []


def test_not_if_the_old_copy_is_what_she_opened_last():
    assert due(recent=("/AO3/old.epub", "/AO3/new.epub")) == []


def test_not_if_the_new_copy_is_gone():
    assert due(present={"/AO3/old.epub"}) == []


def test_never_outside_the_books_folder():
    assert due(copies(old_path="/read/old.epub"), present={"/read/old.epub", "/AO3/new.epub"}) == []


# -- on the sample books -------------------------------------------------------

@needs_samples
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.name)
def test_sample_with_chapters_appended(sample):
    data = sample.read_bytes()
    full = spine_hashes(data)
    old = spine_hashes(truncate_spine(data, len(full) - 3))
    here = Progress(5, 2, 8, 4321)
    p = map_position(old, full, here)
    assert p.exact and p.progress == here
    finished = map_position(old, full, Progress(len(old), 0, 0))
    assert finished.exact and finished.progress == Progress.start_of(len(old))


@needs_samples
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.name)
def test_sample_with_a_chapter_inserted(sample):
    data = sample.read_bytes()
    full = spine_hashes(data)
    new = spine_hashes(insert_item(data, 4, "a chapter the author added"))
    assert map_position(full, new, Progress(6, 1, 3, 99)).progress == Progress(7, 1, 3, 99)
    assert map_position(full, new, Progress(2, 1, 3, 99)).progress == Progress(2, 1, 3, 99)


@needs_samples
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.name)
def test_sample_with_a_chapter_rewritten(sample):
    data = sample.read_bytes()
    full = spine_hashes(data)
    new = spine_hashes(rewrite_item(data, 6, "the author rewrote this chapter"))
    here = Progress(6, 1, 3, 99)
    p = map_position(full, new, here)
    assert not p.exact and p.progress == Progress.start_of(6)
    assert plan_update("auto", CacheState(True, here.to_bytes()), True, full, new).mode == SIDE_BY_SIDE
    # her place in an unchanged chapter of the same update still goes in place
    assert plan_update("auto", CacheState(True, Progress(8, 1, 3).to_bytes()), True, full, new).mode == IN_PLACE
