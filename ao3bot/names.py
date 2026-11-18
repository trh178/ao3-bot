"""File names for books on the reader (DESIGN.md §4.3).

"Author - Title [work_id].epub". The [work_id] keeps names unique and maps a
file back to its work. CrossPoint caps OPDS names at 100 bytes and replaces
/\\:*?"<>| with "_"; pushed files follow the same rule.
"""

from __future__ import annotations

import re
import unicodedata

MAX_NAME_BYTES = 100
_UNSAFE = re.compile(r'[/\\:*?"<>|\x00-\x1f\x7f]')
_SPACES = re.compile(r"\s+")


def device_filename(title: str, authors: list[str], work_id: int, tag: str | None = None) -> str:
    """Return the reader file name for a work, at most MAX_NAME_BYTES of UTF-8.

    `tag` marks a side-by-side copy of a newer revision, e.g. "ch 14" gives
    "Author - Title [123] (ch 14).epub".
    """
    author = ", ".join(a.strip() for a in authors if a.strip()) or "Anonymous"
    stem = _clean(f"{author} - {title.strip() or 'Untitled'}")
    suffix = f" [{work_id}]" + (f" ({_clean(tag)})" if tag else "") + ".epub"
    budget = MAX_NAME_BYTES - len(suffix.encode("utf-8"))
    stem = _truncate_utf8(stem, budget).rstrip(" .")
    return (stem or "Untitled") + suffix


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _SPACES.sub(" ", text)
    text = _UNSAFE.sub("_", text)
    return text.strip(" .")


def _truncate_utf8(text: str, max_bytes: int) -> str:
    """Cut to at most max_bytes of UTF-8, never in the middle of a character."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", "ignore")
