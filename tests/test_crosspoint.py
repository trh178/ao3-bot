import json

import pytest

from ao3bot.crosspoint import Progress, cache_dir, cache_name, cphash, murmur2, recent_paths


def test_murmur2_matches_smhasher():
    # SMHasher's verification test for MurmurHash2 (32-bit): hash the keys
    # {}, {0}, {0,1}, ... {0..254} with seed 256-n, then hash the results with seed 0.
    key = bytes(range(256))
    hashes = b"".join(murmur2(key[:n], 256 - n).to_bytes(4, "little") for n in range(256))
    assert murmur2(hashes, 0) == 0x27864C1E


def test_every_tail_length_counts():
    assert len({murmur2(b"abcd"[:n], 0) for n in range(5)}) == 5


def test_cache_dir_format():
    path = "/AO3/An Author - A Title [123].epub"
    assert cache_dir(path) == f"/.crosspoint/epub_{cphash(path)}"
    assert cache_name(path)[len("epub_"):].isdigit()


def test_the_hash_is_case_sensitive():
    assert cphash("/AO3/x.epub") != cphash("/ao3/x.epub")


def test_the_hash_is_over_utf8():
    assert cphash("/AO3/Zoë.epub") == murmur2("/AO3/Zoë.epub".encode("utf-8"), 0xC70F6907)


@pytest.mark.parametrize("p", [Progress(3, 7), Progress(3, 7, 20), Progress(3, 7, 20, 123456)])
def test_progress_round_trips_in_every_form(p):
    data = p.to_bytes()
    assert len(data) in (4, 6, 10)
    assert Progress.parse(data) == p


def test_progress_layout_is_little_endian():
    data = Progress(0x0102, 0x0304, 0x0506, 0x0708090A).to_bytes()
    assert data == bytes([0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x0A, 0x09, 0x08, 0x07])


@pytest.mark.parametrize("size", [0, 3, 5, 8, 11])
def test_progress_sizes_the_reader_ignores(size):
    assert Progress.parse(bytes(size)) is None


def test_progress_out_of_range():
    with pytest.raises(ValueError):
        Progress(70000, 0).to_bytes()


def test_recent_paths_in_order():
    data = json.dumps({"books": [{"path": "/AO3/a.epub", "title": "A"}, {"path": "/b.epub"}]}).encode()
    assert recent_paths(data) == ["/AO3/a.epub", "/b.epub"]


@pytest.mark.parametrize("data", [None, b"", b"not json", b'{"books": 5}', b"[]", b'{"books": [{"title": "x"}]}'])
def test_recent_paths_tolerates_junk(data):
    assert recent_paths(data) == []
