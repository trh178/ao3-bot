# Phase 6: WIP update planner

**Where:** laptop · **Needs:** 4, 5 · **Unblocks:** 7, 9 · **Target:** week 2

## Task

Write `planner.py`. When a work she has on the reader gets a new revision, it replaces the book **without losing her place**. The full logic is in [DESIGN.md](../DESIGN.md) §5.

- **`cphash(path)`** returns CrossPoint's cache folder name for a book.
  - It's `epub_` followed by libstdc++'s `std::hash<std::string>` of the full SD path, written in decimal.
  - That hash is 32-bit MurmurHash2 with seed `0xc70f6907`.
  - **It's a guess until phase 7.**
- **Read and write `progress.bin`.**
  - The format is little-endian: `u16` chapter (spine index), `u16` page, `u16` page count, then an optional `u32` character offset.
  - Accept files of 4, 6 or 10 bytes. Any other size means the bot doesn't know her position.
- **Chapter mapping:** find the chapter she's in by looking up its text hash in the new revision.
- **Mode 1, in place:**
  1. Read her progress.
  2. Upload the new revision with overwrite.
  3. Recreate the cache folder.
  4. Write the mapped progress.
  5. Read it back to check.
- **Mode 2, side by side:**
  1. Upload `Author - Title [id] (ch 14).epub` next to the old copy.
  2. Seed it with a best-guess position.
  3. Delete the old copy once `/.crosspoint/recent.json` shows she has opened the new one and the grace period has passed.
- **`update_mode = "auto"`** uses Mode 1 only when every check passes, and Mode 2 otherwise.
- **Extend the fake reader** with `/.crosspoint/epub_<hash>/progress.bin` and `recent.json`.

## Done when

- [ ] Unit tests pass for:
  - [ ] a `progress.bin` round trip, in both the 6-byte and 10-byte forms
  - [ ] new chapters appended: same chapter, same offset
  - [ ] a chapter inserted before hers: her chapter index moves up by one
  - [ ] her chapter rewritten: Mode 2
  - [ ] she had finished the book: she lands on the first new chapter
  - [ ] a book never opened (no progress file): a plain overwrite
  - [ ] cleanup: the old copy is deleted only once the new copy is in `recent.json` **and** the grace period has passed, and the book she opened most recently is never deleted
- [ ] End to end against the fake reader: set a position, push an update, and the position is still correct afterwards

## How to test

Use the two revisions from phase 4's chapter-range test as real test data. The fake reader plays the device, including wiping the cache when a book is overwritten.

## How it fits

This is what makes "update and keep her place" work. It's the only part that depends on CrossPoint internals, so phase 7 tests it on the real device before you rely on it. If phase 7 fails, set `update_mode = "side_by_side"` and ship with Mode 2 only. That's still safe for her place.

## Watch out for

- **The hash is a guess until phase 7.** Make sure a wrong hash can only lead to "cache folder not found, use Mode 2", and never to a lost position.
- **Spine indexes include the front matter**, such as the title page and table of contents, not just chapters. Map by spine item. If she's on the title page, keep the same index.
- **Order matters.** Upload first, because the upload is what wipes the cache, and write the progress after. Progress written before the upload gets deleted.
- **Cleanup default:** old copies are deleted automatically 7 days after she opens the new one (`after_switch`). Use `manual` instead if you'd rather she always deletes them herself. Make that call here.
- **A Mode 2 copy keeps its "(ch 14)" name.** Renaming it later would reset her place.
