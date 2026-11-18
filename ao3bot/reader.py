"""Talks to a CrossPoint reader's web API while it's in File Transfer (DESIGN.md §4.1).

Uses only the standard library, and ignores any HTTP proxy settings: the reader
is on the local network, and a proxy would never reach it.
"""

from __future__ import annotations

import http.client
import json
import secrets
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlencode

STATUS_TIMEOUT = 2.0    # "is it in File Transfer?" should answer fast
REQUEST_TIMEOUT = 60.0  # per socket operation; big uploads to an ESP32 are slow


class ReaderUnavailable(Exception):
    """The reader didn't answer, or went away mid-request (she left File Transfer)."""


class ReaderError(Exception):
    """The reader answered with an error."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class FileExists(ReaderError):
    """An upload without overwrite hit a file that's already there."""


@dataclass(frozen=True)
class RemoteFile:
    name: str
    size: int
    is_dir: bool


class ReaderClient:
    def __init__(self, host: str, timeout: float = REQUEST_TIMEOUT):
        self.host = host
        self.base = f"http://{host}"
        self.timeout = timeout
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # -- endpoints ---------------------------------------------------------

    def status(self) -> dict | None:
        """GET /api/status. None means the reader isn't answering."""
        try:
            code, body = self._request("GET", "/api/status", timeout=STATUS_TIMEOUT)
        except ReaderUnavailable:
            return None
        if code != 200:
            return None
        try:
            data = json.loads(body)
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    def list(self, path: str) -> list[RemoteFile]:
        """GET /api/files. A folder that doesn't exist lists as empty, same as the real reader."""
        code, body = self._request("GET", "/api/files", query={"path": path})
        if code != 200:
            raise ReaderError(f"listing {path} failed: {code} {_text(body)}", code)
        try:
            entries = json.loads(body)
        except ValueError:
            raise ReaderError(f"listing {path} returned something that isn't JSON") from None
        return [
            RemoteFile(name=str(e["name"]), size=int(e.get("size", 0)), is_dir=bool(e.get("isDirectory")))
            for e in entries
        ]

    def mkdir(self, parent: str, name: str) -> bool:
        """POST /mkdir. Returns False if the folder was already there."""
        code, body = self._request("POST", "/mkdir", form={"name": name, "path": parent})
        if code == 200:
            return True
        if code == 400 and "already exists" in _text(body):
            return False
        raise ReaderError(f"creating {name} in {parent} failed: {code} {_text(body)}", code)

    def upload(self, folder: str, filename: str, data: bytes, overwrite: bool = False,
               content_type: str = "application/epub+zip") -> None:
        """POST /upload, as multipart field "file"."""
        query = {"path": folder}
        if overwrite:
            query["overwrite"] = "1"
        body, multipart_type = _multipart("file", filename, data, content_type)
        code, reply = self._request("POST", "/upload", query=query, body=body, content_type=multipart_type)
        if code == 200:
            return
        text = _text(reply)
        if code == 400 and text.startswith("File already exists"):
            raise FileExists(text, code)
        raise ReaderError(f"uploading {filename} failed: {code} {text}", code)

    def download(self, path: str) -> bytes | None:
        """GET /download. None if the file isn't there."""
        code, body = self._request("GET", "/download", query={"path": path})
        if code == 200:
            return body
        if code == 404:
            return None
        raise ReaderError(f"downloading {path} failed: {code} {_text(body)}", code)

    def delete(self, path: str) -> None:
        """POST /delete for one file."""
        code, body = self._request("POST", "/delete", form={"path": path})
        if code != 200:
            raise ReaderError(f"deleting {path} failed: {code} {_text(body)}", code)

    # -- plumbing ----------------------------------------------------------

    def _request(self, method: str, path: str, *, query: dict | None = None, form: dict | None = None,
                 body: bytes | None = None, content_type: str | None = None,
                 timeout: float | None = None) -> tuple[int, bytes]:
        url = self.base + path + ("?" + urlencode(query) if query else "")
        headers = {}
        if form is not None:
            body = urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with self._opener.open(request, timeout=timeout or self.timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            reason = getattr(e, "reason", e)
            raise ReaderUnavailable(f"{method} {path}: {reason}") from e


def _multipart(field: str, filename: str, data: bytes, content_type: str) -> tuple[bytes, str]:
    boundary = "ao3bot" + secrets.token_hex(16)
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("ascii")
    return head + data + tail, f"multipart/form-data; boundary={boundary}"


def _text(body: bytes) -> str:
    return body.decode("utf-8", "replace").strip()[:200]
