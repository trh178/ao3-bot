"""A fake CrossPoint reader for tests: the parts of its web API that ao3bot uses.

It copies CrossPoint's behaviour from docs/webserver-endpoints.md and
src/network/CrossPointWebServer.cpp (develop branch, read 2026-11-18):

- GET  /api/status                  JSON, including "device": "X3" | "X4"
- GET  /api/files?path=             JSON list; a missing folder lists as []; dotfiles hidden
- GET  /download?path=              404 "Item not found"; 403 when the last part starts with "."
- POST /upload?path=[&overwrite=1]  multipart field "file"; 400 "File already exists: <name>"
                                    without overwrite; clears the book's cache on success
- POST /mkdir   (form: name, path)  400 "Folder already exists"
- POST /delete  (form: path | paths)

Anything the real reader does differently should be fixed here once phase 7 finds it.

Run it by hand with:  python -m tests.fake_reader --root some/folder --port 8080
"""

from __future__ import annotations

import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HIDDEN_ITEMS = ("System Volume Information", "XTCache")


class FakeReader:
    def __init__(self, root: Path, model: str = "X4", version: str = "2.0.0"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.version = version
        self.show_hidden = False

        # Test hooks
        self.go_away_after_uploads: int | None = None  # stop answering after N successful uploads
        self.drop_response_after_upload = False         # save the next upload, then hang up without a reply
        self.gone = False                               # True: hang up on every request

        # What happened, for assertions
        self.uploads: list[str] = []          # device paths, in order
        self.cleared_caches: list[str] = []   # device paths whose cache the real reader would clear
        self.requests: list[str] = []         # "METHOD /path?query"

        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self, port: int = 0) -> "FakeReader":
        handler = type("Handler", (_Handler,), {"reader": self})
        self._server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def __enter__(self) -> "FakeReader":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    @property
    def host(self) -> str:
        """What goes in [device] host: "127.0.0.1:<port>"."""
        assert self._server, "not started"
        return f"127.0.0.1:{self._server.server_address[1]}"

    # -- the SD card -------------------------------------------------------

    def local(self, device_path: str) -> Path:
        """Map a device path like "/AO3/x.epub" to the file in the fake SD card folder."""
        parts = [p for p in normalize(device_path).split("/") if p]
        if any(p in (".", "..") for p in parts):
            raise ValueError(f"unsafe path {device_path!r}")
        return self.root.joinpath(*parts)


def normalize(path: str) -> str:
    """CrossPoint's normalizeWebPath: leading slash, no trailing slash, "/" for empty."""
    path = path.replace("\\", "/")
    path = re.sub(r"/+", "/", path)
    if not path or path == "/":
        return "/"
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


def is_safe_component(name: str) -> bool:
    """CrossPoint's FsHelpers::isSafePathComponent."""
    return bool(name) and "/" not in name and "\\" not in name and name not in (".", "..")


class _Handler(BaseHTTPRequestHandler):
    reader: FakeReader  # set on the subclass made in FakeReader.start()

    def log_message(self, fmt, *args):  # keep test output quiet
        pass

    # -- plumbing ----------------------------------------------------------

    def _hang_up(self) -> None:
        """Close the connection without a reply, like a reader that left File Transfer."""
        self.close_connection = True

    def _send(self, code: int, body: bytes | str, content_type: str = "text/plain") -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _route(self) -> tuple[str, dict[str, str]]:
        url = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        self.reader.requests.append(f"{self.command} {self.path}")
        return url.path, query

    # -- GET ---------------------------------------------------------------

    def do_GET(self):
        if self.reader.gone:
            return self._hang_up()
        route, query = self._route()
        if route == "/api/status":
            return self._send(200, json.dumps({
                "version": self.reader.version,
                "firmwareFamily": "crosspoint",
                "ip": "127.0.0.1",
                "mode": "STA",
                "rssi": -50,
                "freeHeap": 120000,
                "uptime": 60,
                "device": self.reader.model,
            }), "application/json")
        if route == "/api/files":
            return self._list(normalize(query.get("path", "/")))
        if route == "/download":
            return self._download(query)
        return self._send(404, "Not found")

    def _list(self, path: str) -> None:
        folder = self.reader.local(path)
        entries = []
        if folder.is_dir():
            for child in sorted(folder.iterdir()):
                name = child.name
                if (not self.reader.show_hidden and name.startswith(".")) or name in HIDDEN_ITEMS:
                    continue
                is_dir = child.is_dir()
                entries.append({
                    "name": name,
                    "size": 0 if is_dir else child.stat().st_size,
                    "isDirectory": is_dir,
                    "isEpub": (not is_dir) and name.lower().endswith(".epub"),
                })
        self._send(200, json.dumps(entries), "application/json")

    def _download(self, query: dict[str, str]) -> None:
        if "path" not in query:
            return self._send(400, "Missing path")
        path = normalize(query["path"])
        if path == "/":
            return self._send(400, "Invalid path")
        name = path.rsplit("/", 1)[-1]
        if name.startswith("."):
            return self._send(403, "Cannot access system files")
        if name in HIDDEN_ITEMS:
            return self._send(403, "Cannot access protected items")
        local = self.reader.local(path)
        if not local.exists():
            return self._send(404, "Item not found")
        if local.is_dir():
            return self._send(400, "Path is a directory")
        content_type = "application/epub+zip" if name.lower().endswith(".epub") else "application/octet-stream"
        self._send(200, local.read_bytes(), content_type)

    # -- POST --------------------------------------------------------------

    def do_POST(self):
        if self.reader.gone:
            return self._hang_up()
        route, query = self._route()
        body = self._body()
        if route == "/upload":
            return self._upload(query, body)
        form = {k: v[0] for k, v in parse_qs(body.decode("utf-8"), keep_blank_values=True).items()}
        if route == "/mkdir":
            return self._mkdir(form)
        if route == "/delete":
            return self._delete(form)
        return self._send(404, "Not found")

    def _upload(self, query: dict[str, str], body: bytes) -> None:
        reader = self.reader
        part = _file_part(body, self.headers.get("Content-Type", ""))
        if part is None:
            return self._send(400, "Unknown error during upload")
        filename, data = part
        if not is_safe_component(filename):
            return self._send(400, "Invalid file name")
        folder = normalize(query.get("path", "/"))
        device_path = (folder.rstrip("/") + "/" + filename) if folder != "/" else "/" + filename
        target = reader.local(device_path)
        if target.exists():
            if query.get("overwrite") not in ("1", "true"):
                return self._send(400, f"File already exists: {filename}")
            if target.is_dir():
                return self._send(400, f"A folder with this name already exists: {filename}")
        if not target.parent.is_dir():
            return self._send(400, "Failed to create file on SD card")
        target.write_bytes(data)
        reader.uploads.append(device_path)
        reader.cleared_caches.append(device_path)
        if reader.drop_response_after_upload:
            reader.drop_response_after_upload = False
            return self._hang_up()
        if reader.go_away_after_uploads is not None and len(reader.uploads) >= reader.go_away_after_uploads:
            reader.gone = True
            return self._hang_up()
        self._send(200, f"File uploaded successfully: {filename}")

    def _mkdir(self, form: dict[str, str]) -> None:
        if "name" not in form:
            return self._send(400, "Missing folder name")
        name = form["name"]
        if not name:
            return self._send(400, "Folder name cannot be empty")
        if not is_safe_component(name):
            return self._send(400, "Invalid folder name")
        if name in HIDDEN_ITEMS:
            return self._send(403, "Cannot create protected item")
        parent = normalize(form.get("path", "/"))
        target = self.reader.local(parent).joinpath(name)
        if target.exists():
            return self._send(400, "Folder already exists")
        try:
            target.mkdir()
        except OSError:
            return self._send(500, "Failed to create folder")
        self._send(200, f"Folder created: {name}")

    def _delete(self, form: dict[str, str]) -> None:
        if "path" in form and "paths" in form:
            return self._send(400, "Provide either 'path' or 'paths', not both")
        if "path" in form:
            paths = [form["path"]]
        elif "paths" in form:
            try:
                paths = json.loads(form["paths"])
            except ValueError:
                return self._send(400, "Invalid paths format")
        else:
            return self._send(400, "Missing `path` or `paths` argument")
        if not paths:
            return self._send(400, "No paths provided")
        failed = ""
        for raw in paths:
            path = normalize(str(raw))
            if path == "/":
                failed += f"{path} (cannot delete root); "
                continue
            local = self.reader.local(path)
            if path.rsplit("/", 1)[-1] in HIDDEN_ITEMS:
                failed += f"{path} (protected file); "
            elif not local.exists():
                failed += f"{path} (not found); "
            elif local.is_dir():
                if any(local.iterdir()):
                    failed += f"{path} (folder not empty); "
                else:
                    local.rmdir()
            else:
                local.unlink()
                self.reader.cleared_caches.append(path)
        if failed:
            return self._send(500, f"Failed to delete some items: {failed}")
        self._send(200, "All items deleted successfully")


def _file_part(body: bytes, content_type: str) -> tuple[str, bytes] | None:
    """Return (filename, data) of the multipart part named "file"."""
    match = re.search(r'boundary="?([^";]+)"?', content_type)
    if not match:
        return None
    delimiter = b"--" + match.group(1).encode("latin-1")
    for part in body.split(delimiter)[1:]:
        if part.startswith(b"--"):
            break
        if part.startswith(b"\r\n"):
            part = part[2:]
        head, _, data = part.partition(b"\r\n\r\n")
        if data.endswith(b"\r\n"):
            data = data[:-2]
        disposition = ""
        for line in head.decode("utf-8", "replace").split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                disposition = line
        name = re.search(r'\bname="([^"]*)"', disposition)
        filename = re.search(r'\bfilename="([^"]*)"', disposition)
        if name and name.group(1) == "file" and filename:
            return filename.group(1), data
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a fake CrossPoint reader for manual testing.")
    parser.add_argument("--root", required=True, help="folder that plays the SD card")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--model", default="X4", choices=("X3", "X4"))
    args = parser.parse_args()
    reader = FakeReader(Path(args.root), model=args.model).start(args.port)
    print(f"fake reader on http://{reader.host}  (SD card: {reader.root.resolve()})  Ctrl+C to stop")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        reader.stop()


if __name__ == "__main__":
    main()
