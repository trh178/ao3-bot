# Phase 5: Push to a fake reader

**Where:** laptop · **Needs:** 2 · **Unblocks:** 6, 7, 9 · **Target:** week 2

## Task

Write `push.py` and the `ao3bot push --once` command. Build them against a **fake reader**, a small local HTTP server that copies CrossPoint's web API, so delivery can be built and tested without touching a real reader.

- **The fake reader** (`tests/fake_reader.py`; the standard library's `http.server` is enough):
  - It stores files in a temp folder.
  - It copies these endpoints from CrossPoint's [webserver-endpoints.md](https://github.com/crosspoint-reader/crosspoint-reader/blob/develop/docs/webserver-endpoints.md):
    - `GET /api/status`
    - `GET /api/files?path=`
    - `POST /upload?path=` (multipart field `file`; `overwrite=1` replaces)
    - `GET /download?path=`
    - `POST /mkdir` and `POST /delete`
  - Where it matters, it behaves like the real reader: **overwriting a book deletes that book's `/.crosspoint/epub_<hash>/` folder.**
- **The pusher:**
  1. `GET /api/status` on the configured host, with a 2 s timeout. If there's no answer, the reader isn't in File Transfer, so exit quietly.
  2. Create `/AO3` if it's missing, then list it.
  3. Upload each work whose latest revision isn't on the reader yet, one at a time.
  4. List again and check the name and size, then mark the work delivered in `device_files`.
  5. For now, updates always go side by side (the new copy next to the old one). Phase 6 adds the in-place path.
- **Filenames** follow `Author - Title [work_id].epub`.
  - Replace `/\:*?"<>|` with `_`.
  - Trim trailing dots and spaces.
  - Cap the name at 100 bytes.

## Done when

- [ ] With the fake reader running, `push --once` uploads every built work into `/AO3`
- [ ] A second run uploads nothing
- [ ] If the fake reader stops partway through, nothing crashes, nothing undelivered is marked delivered, and the next run finishes the job
- [ ] The pusher never touches files you add to `/AO3` by hand or files outside `/AO3`
- [ ] Titles with emoji, slashes, or 200 characters still give a valid, unique filename of 100 bytes or less

## How to test

Pytest starts the fake reader on a random port, runs the pusher, and checks the fake reader's folder. It needs no network and no device.

## How it fits

This is the delivery half of the system. Phase 6 adds in-place updates on top of it, and phase 7 points it at the real reader to check that the fake one behaves the same.

## Watch out for

- **Check the exact parameter names** in CrossPoint's endpoint doc: the form fields for mkdir and delete, and the overwrite flag. Write them into the fake reader. Phase 7 confirms them on the device.
- **The fake reader can be wrong.** Anything it does that the real one doesn't will show up in phase 7, so keep it simple and close to the doc.
- **Use exactly the same path string every time.** The reader keys her position on the exact path, including case, even though the SD card ignores case.
- **Cap at 100 bytes, not 100 characters,** and never cut a multi-byte character in half.
- **Upload one file at a time.** The reader has very little memory.
- **Never rename a book she might have opened.** To the reader, a renamed file is a new book with no position.
