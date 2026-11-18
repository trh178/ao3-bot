"""What the bot needs to know about CrossPoint's own files on the SD card (DESIGN.md §5.1).

From CrossPoint's source on `develop`, read 2026-11-18:
- lib/Epub/Epub.cpp: a book's cache folder is
  "/.crosspoint/epub_" + std::to_string(std::hash<std::string>{}(path)),
  where path is the book's full path on the card, exactly as spelled.
- libstdc++ libsupc++/hash_bytes.cc: with a 32-bit size_t (the ESP32-C3), that
  hash is MurmurHash2 with seed 0xc70f6907.
- src/activities/reader/EpubReaderUtils.h and EpubReaderActivity.cpp: the
  progress.bin layout, and "finished" meaning spine >= the spine count.
- src/RecentBooksStore.cpp: recent.json is {"books": [{"path": ...}, ...]},
  most recently opened first.
- src/activities/reader/EpubReaderActivity.cpp: with "move finished books to
  the Read folder" on, a finished book moves to /read, and its cache folder is
  renamed to match the new path.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass

CACHE_ROOT = "/.crosspoint"
RECENT_JSON = "/.crosspoint/recent.json"
READ_FOLDER = "/read"
STD_HASH_SEED = 0xC70F6907

_M = 0x5BD1E995
_MASK = 0xFFFFFFFF


def murmur2(data: bytes, seed: int) -> int:
    """MurmurHash2, 32-bit: libstdc++'s _Hash_bytes when size_t is 32 bits."""
    length = len(data)
    h = (seed ^ length) & _MASK
    i = 0
    while length - i >= 4:
        k = int.from_bytes(data[i:i + 4], "little")
        k = (k * _M) & _MASK
        k ^= k >> 24
        k = (k * _M) & _MASK
        h = (h * _M) & _MASK
        h ^= k
        i += 4
    rest = length - i
    if rest == 3:
        h ^= data[i + 2] << 16
    if rest >= 2:
        h ^= data[i + 1] << 8
    if rest >= 1:
        h ^= data[i]
        h = (h * _M) & _MASK
    h ^= h >> 13
    h = (h * _M) & _MASK
    h ^= h >> 15
    return h


def cphash(path: str) -> int:
    """std::hash<std::string> of a book path, as computed on the reader."""
    return murmur2(path.encode("utf-8"), STD_HASH_SEED)


def cache_name(path: str) -> str:
    """The cache folder's name inside /.crosspoint, e.g. "epub_1234567890"."""
    return f"epub_{cphash(path)}"


def cache_dir(path: str) -> str:
    return f"{CACHE_ROOT}/{cache_name(path)}"


@dataclass(frozen=True)
class Progress:
    """progress.bin: where she is in a book.

    Little-endian u16 spine index, u16 page, then optionally u16 page count, then
    optionally u32 text offset within the chapter. The reader accepts 4, 6 or 10
    bytes, and when the offset is there it wins over the page number.
    """

    spine: int
    page: int
    page_count: int | None = None
    text_offset: int | None = None

    @classmethod
    def parse(cls, data: bytes) -> "Progress | None":
        """None when the size isn't one the reader understands."""
        if len(data) not in (4, 6, 10):
            return None
        spine, page = struct.unpack_from("<HH", data)
        page_count = struct.unpack_from("<H", data, 4)[0] if len(data) >= 6 else None
        text_offset = struct.unpack_from("<I", data, 6)[0] if len(data) == 10 else None
        return cls(spine, page, page_count, text_offset)

    def to_bytes(self) -> bytes:
        if not (0 <= self.spine <= 0xFFFF and 0 <= self.page <= 0xFFFF):
            raise ValueError(f"progress out of range: {self}")
        if self.page_count is None and self.text_offset is None:
            return struct.pack("<HH", self.spine, self.page)
        out = struct.pack("<HHH", self.spine, self.page, self.page_count or 0)
        if self.text_offset is not None:
            out += struct.pack("<I", self.text_offset)
        return out

    @classmethod
    def start_of(cls, spine: int) -> "Progress":
        """The first page of a spine item."""
        return cls(spine, 0, 0)


def recent_paths(data: bytes | None) -> list[str]:
    """Paths from recent.json, most recently opened first. [] if missing or unreadable."""
    if not data:
        return []
    try:
        books = json.loads(data.decode("utf-8")).get("books", [])
        return [str(b["path"]) for b in books if isinstance(b, dict) and b.get("path")]
    except (ValueError, AttributeError, TypeError, UnicodeDecodeError):
        return []
