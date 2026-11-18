import pytest

from ao3bot.names import MAX_NAME_BYTES, device_filename

UNSAFE = '/\\:*?"<>|'


def test_basic_name():
    assert device_filename("A Title", ["An Author"], 123) == "An Author - A Title [123].epub"


def test_several_authors():
    assert device_filename("T", ["Ann", "Bea"], 1) == "Ann, Bea - T [1].epub"


def test_no_author():
    assert device_filename("T", [], 1) == "Anonymous - T [1].epub"


def test_side_by_side_tag():
    assert device_filename("T", ["A"], 1, tag="ch 14") == "A - T [1] (ch 14).epub"


def test_unsafe_characters_replaced():
    name = device_filename('What/If: "Yes"? <3 | \\o/ *', ["A"], 1)
    assert not any(c in name for c in UNSAFE)
    assert name.endswith(" [1].epub")


def test_whitespace_and_control_characters():
    assert device_filename("Line\nBreak\tTab   Spaces", ["A"], 1) == "A - Line Break Tab Spaces [1].epub"


def test_no_leading_dot_or_trailing_dot_space():
    # a leading dot would hide the file; trailing dots and spaces upset FAT
    name = device_filename("Ends with... ", [".hidden"], 1)
    assert name == "hidden - Ends with [1].epub"


def test_unicode_is_normalized():
    assert device_filename("Cafe\u0301", ["Zoe\u0308"], 1) == "Zoë - Café [1].epub"


@pytest.mark.parametrize("title", ["x" * 200, "é" * 120, "💖" * 60, "日本語のタイトル" * 20])
def test_long_names_fit_in_100_bytes(title):
    name = device_filename(title, ["Author"], 123456, tag="ch 140")
    assert len(name.encode("utf-8")) <= MAX_NAME_BYTES
    assert name.endswith(" [123456] (ch 140).epub")
    assert "\ufffd" not in name  # never cut a character in half


def test_same_title_different_works():
    assert device_filename("T", ["A"], 1) != device_filename("T", ["A"], 2)


def test_empty_title():
    assert device_filename("  ", ["A"], 1) == "A - Untitled [1].epub"
