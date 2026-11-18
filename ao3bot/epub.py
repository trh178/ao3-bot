"""Read an EPUB's spine and hash each item's text (DESIGN.md §5.2).

The spine is counted the way CrossPoint counts it
(lib/Epub/Epub/parsers/ContentOpfParser.cpp): every <itemref> whose idref is
in the manifest, in order, whatever its `linear` attribute says. So index N
here is the reader's spine index N.

Each item is hashed on its text, not its bytes, so markup-only changes (a
FanFicFare update re-wrapping the XHTML) don't count as a changed chapter.
Image sources are included, so image-only pages still tell apart.
"""

from __future__ import annotations

import hashlib
import io
import posixpath
import re
import unicodedata
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

_SPACES = re.compile(r"\s+")


class EpubError(Exception):
    """The file isn't an EPUB this code can read."""


def spine_hrefs(epub: bytes | Path) -> list[str]:
    """Zip paths of the spine items, in reading order."""
    with _open(epub) as z:
        return _spine(z)


def spine_hashes(epub: bytes | Path) -> list[str]:
    """One short text hash per spine item, in reading order."""
    with _open(epub) as z:
        names = set(z.namelist())
        return [text_hash(z.read(href) if href in names else b"") for href in _spine(z)]


def text_hash(xhtml: bytes) -> str:
    return hashlib.sha256(_text(xhtml).encode("utf-8")).hexdigest()[:16]


def _open(epub: bytes | Path) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(io.BytesIO(epub) if isinstance(epub, bytes) else epub)
    except (zipfile.BadZipFile, OSError) as e:
        raise EpubError(f"not a zip file: {e}") from None


def _spine(z: zipfile.ZipFile) -> list[str]:
    try:
        container = ElementTree.fromstring(z.read("META-INF/container.xml"))
        rootfile = next(el for el in container.iter() if _local(el.tag) == "rootfile")
        opf_path = rootfile.attrib["full-path"]
        opf = ElementTree.fromstring(z.read(opf_path))
    except (KeyError, StopIteration, ElementTree.ParseError) as e:
        raise EpubError(f"can't find or parse the package file: {e}") from None

    base = posixpath.dirname(opf_path)
    manifest = {}
    for el in opf.iter():
        if _local(el.tag) == "item" and "id" in el.attrib and "href" in el.attrib:
            href = unquote(el.attrib["href"].split("#", 1)[0])
            manifest[el.attrib["id"]] = posixpath.normpath(posixpath.join(base, href)) if base else href
    return [
        manifest[el.attrib["idref"]]
        for el in opf.iter()
        if _local(el.tag) == "itemref" and el.attrib.get("idref") in manifest
    ]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


class _TextCollector(HTMLParser):
    _SKIP = {"head", "script", "style"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skipping += 1
        elif tag in ("img", "image"):
            src = dict(attrs).get("src") or dict(attrs).get("xlink:href") or dict(attrs).get("href") or ""
            self.parts.append(f" [img {posixpath.basename(src)}] ")

    def handle_startendtag(self, tag, attrs):
        if tag not in self._SKIP:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skipping:
            self._skipping -= 1

    def handle_data(self, data):
        if not self._skipping:
            self.parts.append(data)


def _text(xhtml: bytes) -> str:
    collector = _TextCollector()
    collector.feed(xhtml.decode("utf-8", "replace"))
    collector.close()
    text = unicodedata.normalize("NFC", "".join(collector.parts))
    return _SPACES.sub(" ", text).strip()
