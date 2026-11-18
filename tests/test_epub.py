import pytest

from ao3bot.epub import EpubError, spine_hashes, spine_hrefs, text_hash

from .epubs import SAMPLES, _spine_parts, _unzip, insert_item, make_epub, rewrite_item, truncate_spine, xhtml

needs_samples = pytest.mark.skipif(not SAMPLES, reason="no sample EPUBs in the project root")


def test_one_hash_per_spine_item():
    assert len(spine_hashes(make_epub(["one", "two", "three"]))) == 4  # title page + 3 chapters


def test_markup_changes_dont_change_the_hash():
    assert text_hash(xhtml("<p>Hello <b>there</b></p>")) == text_hash(xhtml("<div>Hello\n   there</div>"))


def test_text_changes_do():
    assert text_hash(xhtml("<p>Hello</p>")) != text_hash(xhtml("<p>Hullo</p>"))


def test_the_head_is_ignored():
    assert text_hash(xhtml("<p>x</p>", title="one")) == text_hash(xhtml("<p>x</p>", title="two"))


def test_image_only_pages_tell_apart():
    assert text_hash(xhtml('<img src="a.jpg"/>')) != text_hash(xhtml('<img src="b.jpg"/>'))


def test_appending_a_chapter_keeps_the_earlier_hashes():
    before = spine_hashes(make_epub(["one", "two"]))
    after = spine_hashes(make_epub(["one", "two", "three"]))
    assert before[1:] == after[1:3]
    assert before[0] != after[0]  # the title page shows the chapter count


def test_not_an_epub():
    with pytest.raises(EpubError):
        spine_hashes(b"not a zip")


@needs_samples
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.name)
def test_samples_count_like_the_reader(sample):
    data = sample.read_bytes()
    files, opf_path = _unzip(data)
    _, itemrefs, _ = _spine_parts(files[opf_path].decode("utf-8"))
    hashes = spine_hashes(data)
    assert len(hashes) == len(spine_hrefs(data)) == len(itemrefs)
    assert len(set(hashes)) == len(hashes)  # every item tells apart
    assert spine_hashes(sample) == hashes   # same from a path as from bytes


@needs_samples
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.name)
def test_derived_revisions_of_the_samples(sample):
    data = sample.read_bytes()
    full = spine_hashes(data)
    assert spine_hashes(truncate_spine(data, 5)) == full[:5]
    inserted = spine_hashes(insert_item(data, 3, "a chapter the author added"))
    assert inserted[:3] == full[:3] and inserted[4:] == full[3:] and len(inserted) == len(full) + 1
    rewritten = spine_hashes(rewrite_item(data, 4, "the author rewrote this"))
    assert rewritten[4] != full[4] and rewritten[:4] == full[:4] and rewritten[5:] == full[5:]
