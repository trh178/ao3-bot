"""Phase 6, end to end: WIP updates on the (fake) reader keep her place."""

import pytest

from ao3bot.crosspoint import Progress, cache_dir
from ao3bot.epub import spine_hashes
from ao3bot.push import push_once

from .epubs import SAMPLES, make_epub, truncate_spine
from .helpers import add_revision, add_work, rows

BOOK = "/AO3/An Author - A Work [7].epub"
NAME = BOOK.rsplit("/", 1)[1]
SIDE = "An Author - A Work [7] (ch 4).epub"
HERE = Progress(2, 5, 9, 1234)  # chapter 2 ("two"), page 5 of 9
V1 = ["one", "two", "three"]
V2 = ["one", "two", "three", "four"]


def deliver(cfg, conn, chapters=V1):
    add_work(cfg, conn, 7, "A Work", chapters=len(chapters), data=make_epub(chapters))
    assert push_once(cfg, conn).uploaded == [NAME]


def update(cfg, conn, chapters=V2, rev=2):
    add_revision(cfg, conn, 7, rev=rev, chapters=len(chapters), data=make_epub(chapters))
    return push_once(cfg, conn)


def test_in_place_update_keeps_her_spot(env, reader):
    cfg, conn = env
    deliver(cfg, conn)
    reader.open_book(BOOK, HERE.to_bytes())

    result = update(cfg, conn)
    assert result.replaced == [NAME] and result.uploaded == []
    assert any("unchanged" in n for n in result.notes)
    assert (reader.root / "AO3" / NAME).read_bytes() == make_epub(V2)
    assert reader.progress_of(BOOK) == HERE.to_bytes()
    assert [p.name for p in (reader.root / "AO3").iterdir()] == [NAME]
    old, new = rows(conn)
    assert old["removed_at"] is not None and new["rev"] == 2 and new["path"] == BOOK


def test_finished_book_opens_on_the_new_chapter(env, reader):
    cfg, conn = env
    deliver(cfg, conn)
    reader.open_book(BOOK, Progress(4, 0, 0).to_bytes())  # title page + 3 chapters: spine 4 is the end

    assert update(cfg, conn).replaced == [NAME]
    assert reader.progress_of(BOOK) == Progress.start_of(4).to_bytes()


def test_a_rewritten_chapter_goes_side_by_side(env, reader):
    cfg, conn = env
    deliver(cfg, conn)
    reader.open_book(BOOK, HERE.to_bytes())

    result = update(cfg, conn, chapters=["one", "two, rewritten", "three", "four"])
    assert result.uploaded == [SIDE] and result.replaced == []
    assert (reader.root / "AO3" / NAME).read_bytes() == make_epub(V1)   # old copy untouched...
    assert reader.progress_of(BOOK) == HERE.to_bytes()                  # ...and so is her place in it
    assert reader.progress_of(f"/AO3/{SIDE}") == Progress.start_of(2).to_bytes()  # new copy starts at her chapter


def test_old_copy_is_cleaned_up_once_she_switches(make_env, reader):
    cfg, conn = make_env("cleanup_grace_days = 0")
    deliver(cfg, conn)
    reader.open_book(BOOK, HERE.to_bytes())
    update(cfg, conn, chapters=["one", "two, rewritten", "three", "four"])

    assert push_once(cfg, conn).removed == []           # she hasn't opened the new copy yet
    reader.open_book(f"/AO3/{SIDE}", Progress(2, 1, 9).to_bytes())
    result = push_once(cfg, conn)
    assert result.removed == [NAME]
    assert not (reader.root / "AO3" / NAME).exists()
    assert reader.progress_of(BOOK) is None             # the reader drops a deleted book's cache
    assert rows(conn)[0]["removed_at"] is not None


def test_cleanup_waits_for_the_grace_period(env, reader):
    cfg, conn = env  # 7 days by default
    deliver(cfg, conn)
    reader.open_book(BOOK, HERE.to_bytes())
    update(cfg, conn, chapters=["one", "two, rewritten", "three", "four"])
    reader.open_book(f"/AO3/{SIDE}")
    assert push_once(cfg, conn).removed == []
    assert (reader.root / "AO3" / NAME).exists()


def test_cleanup_never_takes_the_book_she_opened_last(make_env, reader):
    cfg, conn = make_env("cleanup_grace_days = 0")
    deliver(cfg, conn)
    reader.open_book(BOOK, HERE.to_bytes())
    update(cfg, conn, chapters=["one", "two, rewritten", "three", "four"])
    reader.open_book(f"/AO3/{SIDE}")
    reader.open_book(BOOK)  # ...and then went back to the old one
    assert push_once(cfg, conn).removed == []


def test_manual_cleanup_never_deletes(make_env, reader):
    cfg, conn = make_env('cleanup_old = "manual"\ncleanup_grace_days = 0')
    deliver(cfg, conn)
    reader.open_book(BOOK, HERE.to_bytes())
    update(cfg, conn, chapters=["one", "two, rewritten", "three", "four"])
    reader.open_book(f"/AO3/{SIDE}")
    assert push_once(cfg, conn).removed == []


def test_a_never_opened_book_is_replaced_without_writing_a_position(env, reader):
    cfg, conn = env
    deliver(cfg, conn)
    assert update(cfg, conn).replaced == [NAME]
    assert reader.progress_of(BOOK) is None


def test_an_unproven_hash_goes_side_by_side(env, reader):
    cfg, conn = env
    deliver(cfg, conn)
    # recent.json names a book whose cache folder isn't where our hash says, as if
    # the firmware hashed paths differently
    reader._write_recent(["/AO3/Something Else.epub"])
    (reader.local("/.crosspoint") / "epub_12345").mkdir(parents=True)

    result = update(cfg, conn)
    assert result.uploaded == [SIDE] and result.replaced == []
    assert any("cache folder" in n for n in result.notes)
    assert (reader.root / "AO3" / NAME).read_bytes() == make_epub(V1)


def test_an_odd_progress_file_goes_side_by_side(env, reader):
    cfg, conn = env
    deliver(cfg, conn)
    reader.open_book(BOOK, b"\x01\x02\x03\x04\x05\x06\x07")
    assert update(cfg, conn).uploaded == [SIDE]


def test_a_cut_off_in_place_update_is_finished_next_time(env, reader):
    cfg, conn = env
    deliver(cfg, conn)
    reader.open_book(BOOK, HERE.to_bytes())
    reader.go_away_after_uploads = 2  # the new revision lands, then she leaves File Transfer

    first = update(cfg, conn)
    assert first.interrupted
    assert reader.progress_of(BOOK) is None  # the upload wiped her place...

    reader.gone, reader.go_away_after_uploads = False, None
    second = push_once(cfg, conn)
    assert second.replaced == [f"{NAME} (finished an update that was cut off)"]
    assert reader.progress_of(BOOK) == HERE.to_bytes()  # ...and the next run put it back
    assert rows(conn)[-1]["rev"] == 2
    assert conn.execute("SELECT COUNT(*) FROM pending_progress").fetchone()[0] == 0


def test_a_cut_off_update_doesnt_overwrite_a_page_she_read_since(env, reader):
    cfg, conn = env
    deliver(cfg, conn)
    reader.open_book(BOOK, HERE.to_bytes())
    reader.go_away_after_uploads = 2
    update(cfg, conn)

    reader.gone, reader.go_away_after_uploads = False, None
    reader.open_book(BOOK, Progress(3, 1, 4).to_bytes())  # she read on before the next sync
    push_once(cfg, conn)
    assert reader.progress_of(BOOK) == Progress(3, 1, 4).to_bytes()


def test_a_pending_position_for_an_upload_that_never_landed_is_dropped(env, reader):
    cfg, conn = env
    deliver(cfg, conn)
    with conn:
        conn.execute(
            "INSERT INTO pending_progress (device, path, work_id, rev, size, progress, created_at) "
            "VALUES ('test-x4', ?, 7, 2, 1, ?, '2026-11-18T00:00:00Z')",
            (BOOK, HERE.to_bytes()),
        )
    result = push_once(cfg, conn)
    assert result.replaced == []
    assert reader.progress_of(BOOK) is None
    assert conn.execute("SELECT COUNT(*) FROM pending_progress").fetchone()[0] == 0


def test_a_book_moved_to_read_still_gets_updates(env, reader):
    cfg, conn = env
    deliver(cfg, conn)
    reader.open_book(BOOK, Progress(4, 0, 0).to_bytes())  # finished...
    moved = reader.move_to_read(BOOK)                    # ...and the reader moved it to /read

    result = update(cfg, conn)
    assert result.uploaded == [SIDE] and result.skipped == []
    assert any("/read" in n for n in result.notes)
    assert reader.progress_of(f"/AO3/{SIDE}") == Progress.start_of(4).to_bytes()
    assert reader.local(moved).read_bytes() == make_epub(V1)  # the /read copy is left alone


def test_stored_hashes_work_when_the_old_library_file_is_gone(env, reader):
    cfg, conn = env
    add_work(cfg, conn, 7, "A Work", chapters=3, data=make_epub(V1))
    with conn:
        conn.execute("UPDATE revisions SET chapter_hashes = ? WHERE work_id = 7 AND rev = 1",
                     (__import__("json").dumps(spine_hashes(make_epub(V1))),))
    push_once(cfg, conn)
    (cfg.library_dir / "7" / "rev-1.epub").unlink()  # pruned from the library
    reader.open_book(BOOK, HERE.to_bytes())

    assert update(cfg, conn).replaced == [NAME]
    assert reader.progress_of(BOOK) == HERE.to_bytes()


def test_side_by_side_mode_seeds_her_exact_spot(make_env, reader):
    cfg, conn = make_env('update_mode = "side_by_side"')
    deliver(cfg, conn)
    reader.open_book(BOOK, HERE.to_bytes())
    assert update(cfg, conn).uploaded == [SIDE]
    assert reader.progress_of(f"/AO3/{SIDE}") == HERE.to_bytes()


@pytest.mark.skipif(not SAMPLES, reason="no sample EPUBs in the project root")
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.name)
def test_a_real_book_updated_in_place(env, reader, sample):
    """A sample book as revision 1 with its last three items missing, then the full book."""
    cfg, conn = env
    full = sample.read_bytes()
    count = len(spine_hashes(full))
    partial = truncate_spine(full, count - 3)
    add_work(cfg, conn, 99, "Sample", ["Someone"], chapters=count - 3, data=partial)
    push_once(cfg, conn)
    book = "/AO3/Someone - Sample [99].epub"
    here = Progress(5, 3, 11, 2048)
    reader.open_book(book, here.to_bytes())

    add_revision(cfg, conn, 99, rev=2, chapters=count, data=full)
    result = push_once(cfg, conn)
    assert result.replaced == ["Someone - Sample [99].epub"], result
    assert reader.local(book).read_bytes() == full
    assert reader.progress_of(book) == here.to_bytes()
    assert reader.local(cache_dir(book)).is_dir()
