# Phase 4: Build EPUBs

**Where:** laptop · **Needs:** 2 · **Unblocks:** 6, 9 · **Target:** week 1

## Task

Write `build.py` and the `ao3bot build <work_id>` command, which turn a work ID into an EPUB in the library using FanFicFare.

- **Generate FanFicFare's `personal.ini` from `config.toml`.** It needs:
  - the adult-content confirmation
  - images shrunk to `max_image`
  - no update log page
  - the AO3 login, but only once there is one
- **A new work:** run FanFicFare on `https://archiveofourown.org/works/<id>` in a temp folder, then save the result as `library/<id>/rev-1.epub`.
- **An update:** copy the latest revision to `rev-<n+1>.epub`, then run FanFicFare `-u` on the copy. It fetches only the new chapters.
- **Use `--non-interactive`, and `--json-meta`** to get the title, authors, chapter count and completion status.
- **Record in `state.db`:** the revision number, chapter count, the file's sha256, and **a hash of each chapter's text** in `revisions.chapter_hashes`. Use `ao3bot.epub.spine_hashes()`, which phase 6 built, so the hashes match what the planner compares.
- **When pruning old revisions,** keep the `revisions` row of any revision that's still on a reader. The planner needs its chapter hashes even after the file is gone.
- **Keep the last 3 revisions** of each work, and delete older ones.

## Done when

- [ ] `ao3bot build <id>` works for 3–5 public works: a long WIP, one with images, one with an adult warning, and a short finished work
- [ ] Each EPUB opens correctly in a desktop EPUB reader (Calibre's viewer or Thorium), with a title page, every chapter, and images shrunk
- [ ] **Updates work:**
  - Build only the first few chapters of a multi-chapter work, then update it.
  - The new revision has every chapter.
  - The earlier chapters' text hashes haven't changed.
- [ ] Building an unchanged work again creates no new revision
- [ ] A failed build (a bad ID or an AO3 error) leaves the library and `state.db` untouched

## How to test

- **Simulate a WIP update** instead of waiting for an author to post. FanFicFare can fetch a chapter range with `URL[1-3]`; check that the CLI accepts it.
  1. Build chapters 1–3.
  2. Run the update. Chapters 4 onwards arrive as new chapters.
  3. Keep both revisions; phase 6 uses them as test data.
- In a test, compare the two revisions' chapter hashes.
- Read the EPUBs on the laptop. Phase 7 checks them on the real reader.

## How it fits

This phase produces the files that phase 5 pushes. The chapter hashes are what let phase 6 move her reading position to a new revision.

## Watch out for

- **Check FanFicFare's option names in its `defaults.ini`** rather than trusting the ones here. They're likely to be `is_adult`, `include_images`, `image_max_size` and `include_logpage`.
- **Turn the update log page off.** If it's on, every update adds front matter and shifts the chapter positions.
- **Hash the chapter text, not the whole file.** The title page changes on every build, with a new chapter count and date; the chapters shouldn't change.
- **Run FanFicFare in a temp folder.** It writes ini and cache files to the working directory.
- **Pin a FanFicFare version, but plan to update it.** AO3 markup changes break FanFicFare too, and new releases fix them.
- **Huge works** (hundreds of chapters) take a long time and a lot of memory, which matters on the Pi Zero's 512 MB. Note the biggest work you test and how long it took.
