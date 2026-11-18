# Phase 6: WIP update planner

**Status:** ✅ Done Nov 18. Built without AO3 or a real reader, and tested on made-up works and the two sample EPUBs. · **Where:** laptop · **Needs:** 5 (and phase 4's chapter hashes, see below) · **Unblocks:** 7, 9 · **Target:** week 2

## Task

When a work she has on the reader gets a new revision, replace it **without losing her place**. The full logic is in [DESIGN.md](../DESIGN.md) §5.

What was built:
- **`ao3bot/crosspoint.py`** covers CrossPoint's own files on the card:
  - **`cphash(path)`** is libstdc++'s 32-bit `std::hash<std::string>`, which is MurmurHash2 with seed `0xc70f6907`. The cache folder is `/.crosspoint/epub_<hash in decimal>`.
  - `progress.bin` read and write in all three forms: 4, 6 and 10 bytes.
  - `recent.json` parsing.
- **`ao3bot/epub.py`** reads an EPUB's spine the way CrossPoint counts it: every `<itemref>` in the manifest, ignoring `linear`. It hashes each item's **text**, so markup-only changes don't count, and image sources are included.
- **`ao3bot/planner.py`** has no I/O. It contains:
  - `map_position`, which carries her position from one revision to the next by chapter hash
  - `plan_update`, which chooses Mode 1 or Mode 2
  - `hash_trusted`
  - `cleanup_due`
- **`ao3bot/push.py`** now runs updates through the planner:
  - **Mode 1, in place:**
    1. Read `progress.bin`.
    2. Upload with `overwrite=1`. This wipes the cache.
    3. Recreate the cache folder.
    4. Write the mapped position.
    5. Read it back.
  - **Mode 2, side by side:** upload `Author - Title [id] (ch N).epub` next to the old copy, and seed it with a best-guess position.
  - **Cleanup:** delete the old copy once `recent.json` shows she opened the new one and `cleanup_grace_days` have passed.
- **state.db schema v2** adds:
  - `device_files.opened_at`: first seen in `recent.json`
  - `device_files.removed_at`: deleted or replaced by the bot
  - a `pending_progress` table (see below)
- **The fake reader** wipes a book's cache folder on overwrite and delete, like the real one. It can also play her side: `open_book()`, `progress_of()`, `recent()` and `move_to_read()`.

### What CrossPoint's source says (develop, read Nov 18)

| Source | Finding |
|---|---|
| `lib/Epub/Epub.cpp` | Cache folder: `"/.crosspoint/epub_" + std::to_string(std::hash<std::string>{}(path))`, on the full path as spelled. `setupCacheDir()` keeps an existing folder, so a folder holding only our `progress.bin` survives her next open. |
| libstdc++ `hash_bytes.cc` | With a 32-bit `size_t`, `_Hash_bytes` is MurmurHash2. Our port reproduces SMHasher's published MurmurHash2 verification value, `0x27864C1E`. |
| `EpubReaderUtils.h`, `ProgressFile.h` | `progress.bin` is written atomically, through `progress.bin.tmp`. |
| `EpubReaderActivity.cpp` | It reads 4, 6 or 10 bytes and ignores any other size. **End of book is `spine >= spine count`.** |
| `RecentBooksStore.cpp` | `recent.json` is `{"books":[{"path","title","author","coverBmpPath"}]}`, newest first, 10 at most. |
| `ContentOpfParser.cpp` | The spine is every `itemref` whose `idref` is in the manifest. `linear` is ignored. |
| `EpubReaderActivity.cpp` | **There's a "Move finished books to Read folder" setting** (off by default). A finished book moves to `/read`, its cache folder is renamed, and `recent.json` is updated. |

### Decisions made while building it

- **`auto` replaces in place only when it's certain.** That means one of:
  - her chapter's text is unchanged in the new revision (inserted chapters before hers are fine)
  - she'd finished the book, so it opens on the first new chapter
  - she was in front matter that changed, so it opens at the start of that item

  Everything else goes side by side.
- **A missing cache folder means "never opened" only when the hash is proven on this reader.** That's the case when a book in `recent.json` has its folder where `cphash` says, or when there are no cache folders at all. Otherwise the update goes side by side.
  - This is the safety net if the hash turns out wrong on the device: updates still arrive, as side-by-side copies, and no position is ever lost.
  - `update_mode = "in_place"` follows the same rule.
- **`in_place` mode** replaces even when her chapter was rewritten, landing at the start of that chapter. `side_by_side` mode always adds a copy, still seeded with her position.
- **Cut-off updates are finished on the next run.** Before an in-place upload, the position to write goes into `pending_progress`. If she leaves File Transfer after the upload lands but before the position is written, the next run writes it, unless she has opened the book and saved a newer page since. If the upload never landed, nothing was lost and the row is dropped.
- **Cleanup keeps old copies in these cases:**
  - the new copy is gone (she deleted it)
  - the old copy is the book she opened most recently
  - the old copy is outside the books folder

  A book the reader moved to `/read` still gets updates, as a new copy in `/AO3`, and the `/read` copy is left alone.
- **Cleanup default:** delete the old copy 7 days after she opens the new one (`after_switch`). `manual` never deletes.

## Done when

- [x] Unit tests pass for:
  - [x] a `progress.bin` round trip, in the 4-, 6- and 10-byte forms
  - [x] new chapters appended: same chapter, same offset
  - [x] a chapter inserted before hers: her chapter index moves up by one
  - [x] her chapter rewritten: Mode 2
  - [x] she had finished the book: she lands on the first new chapter
  - [x] a book never opened (no progress file): a plain overwrite
  - [x] cleanup: the old copy is deleted only once the new copy is in `recent.json` **and** the grace period has passed, and the book she opened most recently is never deleted
- [x] End to end against the fake reader: set a position, push an update, and the position is still correct afterwards. This was checked on made-up works and on both sample books, through `pytest` and through `ao3bot push --once` as its own process.

## How to test

- **`pytest`:** 171 tests, about 20 s, all on localhost.
  - **Sample books:** 12 of them use the `*.epub` files in the project root. `tests/epubs.py` turns a sample into "revisions" by cutting the spine short, inserting an item, or rewriting one.
  - **Without the samples** (e.g. on another computer), those 12 are skipped and the other 159 still run.
- **By hand:** the Nov 18 check used one sample book as two works:
  - **Work 1 (appended chapters):** after the update, the reader showed `replaced`, with "her chapter is unchanged" as the reason. Her place was still chapter 5, page 3, offset 2048.
  - **Work 2 (rewritten chapter):** the update arrived as a `(ch 21)` copy, seeded at the start of her chapter. Her place in the old copy was untouched.
  - **Cleanup:** once she opened the new copy (grace 0 days), the old one was removed.

## How it fits

This is what makes "update and keep her place" work, and it's the only part that depends on CrossPoint internals. Phase 7 steps 5–9 test it on the real device before you rely on it. If phase 7 fails, set `update_mode = "side_by_side"` and ship with Mode 2 only. That's still safe for her place.

Phase 4 should store each revision's `chapter_hashes` using `ao3bot.epub.spine_hashes`. The planner falls back to reading the library file, but stored hashes keep working after old revisions are pruned.

## Watch out for

- **The hash is proven as MurmurHash2, but not yet on the device.** The open question is whether the reader hashes exactly the path string the bot uses. A wrong hash can only push updates side by side; it can never lose her position.
- **Spine indexes include the front matter** (title page, table of contents), not just chapters. Mapping is by spine item.
- **Order matters.** Upload first, because the upload is what wipes the cache, then write the progress.
- **"Move finished books to Read folder"** is handled, but simpler with it off, which is the default. Leave it off on her reader.
- **A Mode 2 copy keeps its "(ch N)" name.** Renaming it later would reset her place.
- **The fake reader uses the same `cphash` as the bot,** so the tests can't catch a wrong hash. That's exactly what phase 7 step 5 is for.
