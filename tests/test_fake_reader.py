"""The fake reader, driven through ao3bot's own client, behaves like CrossPoint's source says."""

import pytest

from ao3bot.reader import FileExists, ReaderClient, ReaderError


@pytest.fixture
def client(reader):
    return ReaderClient(reader.host)


def test_status_reports_the_model(client):
    status = client.status()
    assert status["device"] == "X4"
    assert status["firmwareFamily"] == "crosspoint"


def test_status_is_none_when_nobody_answers(reader, client):
    reader.stop()
    assert client.status() is None


def test_a_missing_folder_lists_as_empty(client):
    assert client.list("/Nope") == []


def test_mkdir_twice(client):
    assert client.mkdir("/", "AO3") is True
    assert client.mkdir("/", "AO3") is False


def test_upload_needs_the_folder_to_exist(client):
    with pytest.raises(ReaderError, match="Failed to create file"):
        client.upload("/Nope", "a.epub", b"x")


def test_upload_never_overwrites_by_default(reader, client):
    client.mkdir("/", "AO3")
    client.upload("/AO3", "a.epub", b"one")
    with pytest.raises(FileExists):
        client.upload("/AO3", "a.epub", b"two")
    assert (reader.root / "AO3" / "a.epub").read_bytes() == b"one"
    client.upload("/AO3", "a.epub", b"two", overwrite=True)
    assert (reader.root / "AO3" / "a.epub").read_bytes() == b"two"
    assert reader.cleared_caches == ["/AO3/a.epub", "/AO3/a.epub"]


def test_unsafe_name_is_rejected(client):
    with pytest.raises(ReaderError, match="Invalid file name"):
        client.upload("/", "a\\b.epub", b"x")


def test_listing_shows_sizes_and_folders(client):
    client.mkdir("/", "AO3")
    client.upload("/AO3", "a.epub", b"12345")
    client.mkdir("/AO3", "sub")
    entries = {f.name: f for f in client.list("/AO3")}
    assert entries["a.epub"].size == 5 and not entries["a.epub"].is_dir
    assert entries["sub"].is_dir


def test_hidden_items_are_not_listed(reader, client):
    (reader.root / ".crosspoint").mkdir()
    (reader.root / "System Volume Information").mkdir()
    (reader.root / "AO3").mkdir()
    assert [f.name for f in client.list("/")] == ["AO3"]


def test_download_and_delete(client):
    client.mkdir("/", "AO3")
    client.upload("/AO3", "a.epub", b"data")
    assert client.download("/AO3/a.epub") == b"data"
    client.delete("/AO3/a.epub")
    assert client.download("/AO3/a.epub") is None


def test_dot_named_files_cannot_be_downloaded(reader, client):
    (reader.root / ".secret").write_bytes(b"x")
    with pytest.raises(ReaderError) as e:
        client.download("/.secret")
    assert e.value.status == 403


def test_files_inside_the_cache_folder_can_be_downloaded(reader, client):
    # Phase 6 relies on this: only the last path part is checked for a leading dot
    progress = reader.root / ".crosspoint" / "epub_123" / "progress.bin"
    progress.parent.mkdir(parents=True)
    progress.write_bytes(b"\x01\x00\x02\x00\x03\x00")
    assert client.download("/.crosspoint/epub_123/progress.bin") == b"\x01\x00\x02\x00\x03\x00"


def test_non_ascii_names_round_trip(client):
    client.mkdir("/", "AO3")
    name = "Zoë - Café 💖 [1].epub"
    client.upload("/AO3", name, b"x")
    assert [f.name for f in client.list("/AO3")] == [name]


def test_deleting_a_folder_that_is_not_empty_fails(client):
    client.mkdir("/", "AO3")
    client.upload("/AO3", "a.epub", b"x")
    with pytest.raises(ReaderError, match="folder not empty"):
        client.delete("/AO3")


def test_overwriting_a_book_wipes_its_cache_folder(reader, client):
    client.mkdir("/", "AO3")
    client.upload("/AO3", "a.epub", b"one")
    reader.open_book("/AO3/a.epub", b"\x02\x00\x05\x00\x09\x00")
    assert reader.progress_of("/AO3/a.epub") is not None
    client.upload("/AO3", "a.epub", b"two", overwrite=True)
    assert reader.progress_of("/AO3/a.epub") is None


def test_deleting_a_book_wipes_its_cache_folder(reader, client):
    client.mkdir("/", "AO3")
    client.upload("/AO3", "a.epub", b"one")
    reader.open_book("/AO3/a.epub", b"\x02\x00\x05\x00\x09\x00")
    client.delete("/AO3/a.epub")
    assert reader.progress_of("/AO3/a.epub") is None


def test_the_cache_folder_lists_and_recent_json_downloads(reader, client):
    client.mkdir("/", "AO3")
    client.upload("/AO3", "a.epub", b"one")
    reader.open_book("/AO3/a.epub")
    names = {f.name for f in client.list("/.crosspoint")}
    assert "recent.json" in names and any(n.startswith("epub_") for n in names)
    assert b"/AO3/a.epub" in client.download("/.crosspoint/recent.json")


def test_move_to_read_takes_the_cache_along(reader, client):
    client.mkdir("/", "AO3")
    client.upload("/AO3", "a.epub", b"one")
    reader.open_book("/AO3/a.epub", b"\x02\x00\x05\x00\x09\x00")
    moved = reader.move_to_read("/AO3/a.epub")
    assert moved == "/read/a.epub"
    assert reader.progress_of(moved) == b"\x02\x00\x05\x00\x09\x00"
    assert reader.recent() == ["/read/a.epub"]
