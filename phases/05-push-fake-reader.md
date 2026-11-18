# Phase 5: Push to a fake reader

**Status:** ✅ Done Nov 18. Nothing touched AO3 or a real reader. · **Where:** laptop · **Needs:** 2 · **Unblocks:** 6, 7, 9 · **Target:** week 2

## Task

Write the `ao3bot push` command. Build it against a **fake reader**, a small local HTTP server that copies CrossPoint's web API, so delivery can be built and tested without touching a real reader.

What was built:
- **`ao3bot/reader.py`** is the client for the reader's web API (status, list, mkdir, upload, download, delete).
  - It uses only the standard library.
  - It ignores proxy settings, because a proxy can't reach a LAN device.
- **`ao3bot/names.py`** builds filenames: `Author - Title [work_id].epub`.
  - It replaces `/\:*?"<>|` and control characters with `_`, and collapses whitespace.
  - It strips leading and trailing dots and spaces, and normalizes Unicode (NFC).
  - It caps the name at 100 bytes of UTF‑8 without splitting a character. The ` [work_id].epub` suffix is never cut.
- **`ao3bot/push.py`** does the delivery:
  1. `GET /api/status` with a 2 s timeout. If there's no answer, the reader isn't in File Transfer, so it stops quietly.
  2. Find `/AO3` by listing its parent folder, and create it if it's missing. If the card already has it with different capitals (e.g. `/ao3`), use that spelling.
  3. Upload each work whose newest revision isn't on the reader yet, one at a time, never overwriting.
  4. List the folder again, check the name and size, then record the file in `device_files`.
  5. Updates go side by side as `Author - Title [id] (ch N).epub`, next to the old copy. Phase 6 adds in-place updates and cleanup.
- **`ao3bot push --once`** pushes once and prints a report. Plain **`ao3bot push`** checks for the reader every 60 s (`--interval`) until Ctrl+C, and prints only when something happened.
- **`tests/fake_reader.py`** is the fake reader. It can also run by hand (see How to test).

### What CrossPoint's source says, and the fake copies

From `docs/webserver-endpoints.md` and `src/network/CrossPointWebServer.cpp` on `develop`, read Nov 18:

| Endpoint | Behaviour that matters |
|---|---|
| `GET /api/status` | JSON that includes `"device": "X3"` or `"X4"` and `"version"`, so the bot can tell your two readers apart |
| `GET /api/files?path=` | `[{name, size, isDirectory, isEpub}]`. **A folder that doesn't exist lists as `[]`**, so check the parent to know whether a folder exists. Dotfiles are hidden. |
| `POST /upload?path=` | Multipart field `file`. **Without `overwrite=1`, an existing file gives a 400 "File already exists".** A missing folder gives a 400 "Failed to create file on SD card". The filename can't contain `/` or `\`. Success clears that book's cache. |
| `POST /mkdir` | Form fields `name` and `path` (the parent). An existing folder gives a 400 "Folder already exists". |
| `GET /download?path=` | 404 if the file is missing, and 403 if **the last part** of the path starts with `.`. So `/.crosspoint/epub_…/progress.bin` can be downloaded, which phase 6 needs. |
| `POST /delete` | Form field `path` (or a `paths` JSON list). It won't delete a folder that isn't empty. |

The fake records the paths whose cache the real reader would clear, but it doesn't delete a cache folder yet. That needs CrossPoint's cache-folder hash, which phase 6 adds.

### Decisions made while building it

- **A book she deleted on the reader is never sent again,** not even when a newer revision comes out. Her delete means she's done with it.
- **A file already on the reader under the bot's name** is adopted when its size matches; that happens when a run was cut off after the upload but before it was recorded. If the size doesn't match, the file is left alone and reported.
- **Files are recorded per reader,** using `[device] name`, so the test reader and her reader keep separate records.

## Done when

- [x] With the fake reader running, `push --once` uploads every built work into `/AO3`
- [x] A second run uploads nothing
- [x] If the fake reader stops partway through, nothing crashes, nothing undelivered is marked delivered, and the next run finishes the job. That includes the case where the upload landed but the reply was lost.
- [x] The pusher never touches files you add to `/AO3` by hand or files outside `/AO3`, including a file that happens to have the bot's name
- [x] Titles with emoji, slashes, or 200 characters still give a valid, unique filename of 100 bytes or less

## How to test

- **`pytest`:** 81 tests, about 10 s. There are 40 new ones: filenames, fake-reader behaviour checked through the real client, and the push scenarios above. The fake reader runs on `127.0.0.1`. The network guard blocks anything else, so the tests can't reach AO3.
- **By hand, in two terminals:**
  ```bash
  python -m tests.fake_reader --root fake-sd --port 8080
  ```
  Then point `[device] host` at `127.0.0.1:8080` and run `ao3bot push --once`. Until phase 4 exists, nothing is built to send. The end-to-end check on Nov 18 seeded `state.db` with a script, and `ao3bot push --once` uploaded two works, then nothing on the second run.

## How it fits

This is the delivery half of the system. Phase 6 adds in-place updates on top of it, using `ReaderClient.download` and `.delete`, which are already here. Phase 7 points the pusher at the real reader to check that the fake one behaves the same.

## Watch out for

- **The fake reader can be wrong.** It follows the source, not the device. Phase 7 step 3 checks the table above on real hardware, and anything that differs gets fixed in `tests/fake_reader.py` first.
- **Use exactly the same path string every time.** The reader keys her position on the exact path, including case, even though the SD card ignores case. The path is worked out once at upload, stored in `device_files`, and never rebuilt.
- **Upload one file at a time.** The reader has very little memory.
- **Never rename a book she might have opened.** To the reader, a renamed file is a new book with no position.
- **Emoji in filenames** are valid on the SD card, but the reader's file browser font may not draw them. Check this in phase 7 step 4. The Library shows the title from inside the EPUB, so it should be fine there.
- **Windows is slow to refuse a connection** to a port nothing is listening on, about 2 s. That's why the three "reader is off" tests each take around 2.5 s.
