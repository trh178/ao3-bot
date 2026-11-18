"""EPUBs for tests: small made-up works, and revisions derived from real sample books.

make_epub() builds a FanFicFare-like work: a title page that mentions the
chapter count (so it changes on every update, like the real thing), then one
file per chapter.

truncate_spine(), insert_item() and rewrite_item() turn a real EPUB into
"another revision" of itself, so the planner can be tested on real-world
package files. The sample books are the *.epub files dropped in the project
root. They're gitignored, and SAMPLES is empty when there aren't any.
"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from pathlib import Path

from ao3bot.epub import spine_hrefs

REPO = Path(__file__).resolve().parent.parent
SAMPLES = sorted(REPO.glob("*.epub"))

_CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""


def xhtml(body: str, title: str = "x") -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>'
        f"{title}</title></head><body>{body}</body></html>"
    ).encode("utf-8")


def make_epub(chapters: list[str], title: str = "A Work", author: str = "An Author") -> bytes:
    pages = [("title", f"<h1>{title}</h1><p>by {author}</p><p>Chapters: {len(chapters)}/?</p>")]
    pages += [(f"file{i + 1:04d}", f"<h2>Chapter {i + 1}</h2><p>{text}</p>") for i, text in enumerate(chapters)]
    manifest = "".join(
        f'<item id="{pid}" href="{pid}.xhtml" media-type="application/xhtml+xml"/>' for pid, _ in pages
    )
    spine = "".join(f'<itemref idref="{pid}"/>' for pid, _ in pages)
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">'
        f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{title}</dc:title></metadata>'
        f"<manifest>{manifest}</manifest><spine>{spine}</spine></package>"
    )
    files = {"META-INF/container.xml": _CONTAINER.encode(), "OEBPS/content.opf": opf.encode()}
    files.update({f"OEBPS/{pid}.xhtml": xhtml(body, title) for pid, body in pages})
    return _zip(files)


# -- revisions of a real book --------------------------------------------------

def truncate_spine(epub: bytes, keep: int) -> bytes:
    """The same book, with only its first `keep` spine items in the spine."""
    files, opf_path = _unzip(epub)
    opf = files[opf_path].decode("utf-8")
    head, refs, tail = _spine_parts(opf)
    files[opf_path] = (head + "".join(refs[:keep]) + tail).encode("utf-8")
    return _zip(files)


def insert_item(epub: bytes, index: int, text: str) -> bytes:
    """The same book, with a new spine item placed before spine index `index`."""
    files, opf_path = _unzip(epub)
    opf = files[opf_path].decode("utf-8")
    opf = opf.replace("</manifest>", '<item id="ao3bot-inserted" href="ao3bot-inserted.xhtml" '
                                     'media-type="application/xhtml+xml"/></manifest>', 1)
    head, refs, tail = _spine_parts(opf)
    refs.insert(index, '<itemref idref="ao3bot-inserted"/>')
    files[opf_path] = (head + "".join(refs) + tail).encode("utf-8")
    files[posixpath.join(posixpath.dirname(opf_path), "ao3bot-inserted.xhtml")] = xhtml(f"<p>{text}</p>")
    return _zip(files)


def rewrite_item(epub: bytes, index: int, text: str) -> bytes:
    """The same book, with spine item `index` replaced by different text."""
    files, _ = _unzip(epub)
    files[spine_hrefs(epub)[index]] = xhtml(f"<p>{text}</p>")
    return _zip(files)


def _spine_parts(opf: str) -> tuple[str, list[str], str]:
    match = re.search(r"(<(?:\w+:)?spine\b[^>]*>)(.*?)(</(?:\w+:)?spine>)", opf, re.S)
    if not match:
        raise ValueError("no <spine> in the package file")
    refs = re.findall(r"<(?:\w+:)?itemref\b[^>]*?(?:/>|>\s*</(?:\w+:)?itemref>)", match.group(2))
    if not refs:
        raise ValueError("no <itemref> in the spine")
    return opf[:match.end(1)], refs, opf[match.start(3):]


def _unzip(epub: bytes) -> tuple[dict[str, bytes], str]:
    with zipfile.ZipFile(io.BytesIO(epub)) as z:
        files = {name: z.read(name) for name in z.namelist()}
    container = files["META-INF/container.xml"].decode("utf-8")
    opf_path = re.search(r'full-path="([^"]+)"', container).group(1)
    return files, opf_path


def _zip(files: dict[str, bytes]) -> bytes:
    """Zip deterministically: fixed timestamps, so the same files always give the same bytes."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(_entry("mimetype", zipfile.ZIP_STORED), b"application/epub+zip")
        for name, data in files.items():
            if name != "mimetype":
                z.writestr(_entry(name, zipfile.ZIP_DEFLATED), data)
    return out.getvalue()


def _entry(name: str, compression: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = compression
    return info
