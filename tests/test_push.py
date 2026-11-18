"""Phase 5: getting new works onto the reader, and the rules for what's never touched."""

from ao3bot.cli import main
from ao3bot.push import push_once

from .helpers import add_revision, add_work, placeholder_epub, rows


def test_unreachable_reader_changes_nothing(env, reader):
    cfg, conn = env
    add_work(cfg, conn, 1)
    reader.stop()
    result = push_once(cfg, conn)
    assert not result.reachable
    assert rows(conn) == []


def test_pushes_every_built_work(env, reader):
    cfg, conn = env
    add_work(cfg, conn, 101, "First", ["Ann"])
    add_work(cfg, conn, 102, "Second", ["Bea"])
    result = push_once(cfg, conn)
    assert result.reachable and result.model == "X4" and result.folder == "/AO3"
    assert result.uploaded == ["Ann - First [101].epub", "Bea - Second [102].epub"]
    assert result.errors == []
    assert (reader.root / "AO3").is_dir()
    assert (reader.root / "AO3" / "Ann - First [101].epub").read_bytes() == placeholder_epub(101, 1)
    recorded = rows(conn)
    assert [r["path"] for r in recorded] == ["/AO3/Ann - First [101].epub", "/AO3/Bea - Second [102].epub"]
    assert {r["device"] for r in recorded} == {"test-x4"}


def test_second_run_uploads_nothing(env, reader):
    cfg, conn = env
    add_work(cfg, conn, 1)
    push_once(cfg, conn)
    again = push_once(cfg, conn)
    assert again.uploaded == [] and not again.eventful
    assert len(reader.uploads) == 1


def test_reader_going_away_midway_finishes_next_time(env, reader):
    cfg, conn = env
    for i in (1, 2, 3):
        add_work(cfg, conn, i, f"T{i}")
    reader.go_away_after_uploads = 2  # T2 lands on the card, but the reply never comes back

    first = push_once(cfg, conn)
    assert first.interrupted
    assert first.uploaded == ["An Author - T1 [1].epub"]
    assert len(rows(conn)) == 1  # nothing recorded that wasn't confirmed

    reader.gone, reader.go_away_after_uploads = False, None  # she opens File Transfer again
    second = push_once(cfg, conn)
    assert second.adopted == ["An Author - T2 [2].epub"]  # already there, same size: no re-upload
    assert second.uploaded == ["An Author - T3 [3].epub"]
    assert len(rows(conn)) == 3
    assert reader.uploads.count("/AO3/An Author - T2 [2].epub") == 1


def test_files_that_are_not_ours_are_never_touched(env, reader):
    cfg, conn = env
    other = reader.root / "Other" / "book.epub"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"hers")
    (reader.root / "AO3").mkdir()
    hand_copied = reader.root / "AO3" / "Her Own Book.epub"
    hand_copied.write_bytes(b"hand copied")
    clash = reader.root / "AO3" / "An Author - Clash [5].epub"
    clash.write_bytes(b"something else entirely")
    add_work(cfg, conn, 5, "Clash")
    add_work(cfg, conn, 6, "Fine")

    result = push_once(cfg, conn)
    assert result.uploaded == ["An Author - Fine [6].epub"]
    assert any("Clash [5]" in s and "left alone" in s for s in result.skipped)
    assert other.read_bytes() == b"hers"
    assert hand_copied.read_bytes() == b"hand copied"
    assert clash.read_bytes() == b"something else entirely"
    assert reader.uploads == ["/AO3/An Author - Fine [6].epub"]


def test_auto_replaces_a_never_opened_book_in_place(env, reader):
    cfg, conn = env
    add_work(cfg, conn, 7, "Wip", chapters=3)
    push_once(cfg, conn)
    add_revision(cfg, conn, 7, rev=2, chapters=4)

    result = push_once(cfg, conn)
    assert result.replaced == ["An Author - Wip [7].epub"]
    assert [p.name for p in (reader.root / "AO3").iterdir()] == ["An Author - Wip [7].epub"]
    assert (reader.root / "AO3" / "An Author - Wip [7].epub").read_bytes() == placeholder_epub(7, 2)
    old, new = rows(conn)
    assert old["removed_at"] is not None and new["rev"] == 2 and new["removed_at"] is None


def test_side_by_side_mode_keeps_the_old_copy(make_env, reader):
    cfg, conn = make_env('update_mode = "side_by_side"')
    add_work(cfg, conn, 7, "Wip", chapters=3)
    push_once(cfg, conn)
    add_revision(cfg, conn, 7, rev=2, chapters=4)

    result = push_once(cfg, conn)
    assert result.uploaded == ["An Author - Wip [7] (ch 4).epub"]
    assert (reader.root / "AO3" / "An Author - Wip [7].epub").read_bytes() == placeholder_epub(7, 1)
    old, new = rows(conn)
    assert old["rev"] == 1 and old["superseded_at"] is not None and old["removed_at"] is None
    assert new["rev"] == 2 and new["superseded_at"] is None


def test_an_edit_that_keeps_the_chapter_count_gets_its_own_name(make_env):
    cfg, conn = make_env('update_mode = "side_by_side"')
    add_work(cfg, conn, 8, "Edited", chapters=3)
    push_once(cfg, conn)
    add_revision(cfg, conn, 8, rev=2, chapters=4)
    push_once(cfg, conn)
    add_revision(cfg, conn, 8, rev=3, chapters=4)
    result = push_once(cfg, conn)
    assert result.uploaded == ["An Author - Edited [8] (ch 4, rev 3).epub"]


def test_a_book_she_deleted_is_not_sent_again(env, reader):
    cfg, conn = env
    add_work(cfg, conn, 9, "Gone")
    push_once(cfg, conn)
    (reader.root / "AO3" / "An Author - Gone [9].epub").unlink()  # long-press, Delete

    assert not push_once(cfg, conn).eventful
    add_revision(cfg, conn, 9, rev=2, chapters=5)
    result = push_once(cfg, conn)
    assert result.uploaded == [] and result.replaced == []
    assert any("deleted on the reader" in s for s in result.skipped)


def test_the_readers_spelling_of_the_folder_is_used(env, reader):
    cfg, conn = env
    (reader.root / "ao3").mkdir()
    add_work(cfg, conn, 10, "Case")
    result = push_once(cfg, conn)
    assert result.folder == "/ao3"
    assert rows(conn)[0]["path"] == "/ao3/An Author - Case [10].epub"


def test_a_missing_library_file_is_an_error_but_others_still_go(env):
    cfg, conn = env
    add_work(cfg, conn, 11, "Lost")
    (cfg.library_dir / "11" / "rev-1.epub").unlink()
    add_work(cfg, conn, 12, "Here")
    result = push_once(cfg, conn)
    assert any("library file missing" in e for e in result.errors)
    assert result.uploaded == ["An Author - Here [12].epub"]


def test_books_folder_that_is_a_file(env, reader):
    cfg, conn = env
    (reader.root / "AO3").write_bytes(b"oops")
    add_work(cfg, conn, 13)
    result = push_once(cfg, conn)
    assert result.errors == ["/AO3 on the reader is a file, not a folder"]
    assert rows(conn) == []


def test_cli_push_once(env, capsys):
    cfg, conn = env
    add_work(cfg, conn, 14, "Cli")
    assert main(["--config", str(cfg.path), "push", "--once"]) == 0
    out = capsys.readouterr().out
    assert "uploaded    An Author - Cli [14].epub" in out
    assert "done: 1 uploaded" in out


def test_cli_push_when_reader_is_off(env, reader, capsys):
    cfg, _ = env
    reader.stop()
    assert main(["--config", str(cfg.path), "push", "--once"]) == 0
    assert "isn't answering" in capsys.readouterr().out
