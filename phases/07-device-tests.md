# Phase 7: Real device tests

**Where:** laptop + readers · **Needs:** 5 and 6 (steps 1–3 need nothing, so do them any time) · **Unblocks:** 9 · **Target:** week 2 (Nov 24–30)

## Task

Flash CrossPoint, then check everything the software assumes about the reader. Run the pusher from the laptop against the real device. This is the go/no-go for in-place updates.

**First, decide which reader is hers.** The other one is the test reader, and every step below runs on it. On her reader, do only steps 1, 2 and 4: flash it, put it on the Wi‑Fi, and check rendering, since the X3 and X4 have different screens. That keeps her reader clean until the welcome batch in phase 10.

1. **Flash** CrossPoint 2.0.x, following its README. Note the version.
2. **Network:**
   - Open File Transfer → Join Network on the home Wi‑Fi.
   - Give the reader a DHCP reservation in the router.
   - Check that `GET http://<ip>/api/status` works from the laptop.
3. **API:** check that upload, list, download, overwrite, mkdir and delete behave the way the fake reader does. Wherever they differ, fix the fake reader.
4. **Rendering:** open the phase 4 test EPUBs, including one with images, a long work, and one with an adult warning. Note anything slow or broken.
5. **Cache hash:** upload a book, open it, then list `/.crosspoint`. Is there an `epub_<cphash(path)>` folder?
6. **Progress format:** read a book to the middle of chapter 3, then download and decode its `progress.bin`. Does it say chapter 3?
7. **Mode 1:** push the next revision of that book in place, then open it. Is it at the same spot?
8. **Finished book:** finish a book, push a revision with a new chapter, then open it. Does it open on the new chapter?
9. **Mode 2 cleanup:** push a revision side by side and open the new copy. Does `recent.json` list it?
10. **Overnight:**
    - Put the reader on the charger in File Transfer.
    - Have the laptop call `/api/status` every 60 s all night, the same rate the Pi will use.
    - Is it still answering in the morning?

## Done when

- [ ] Steps 1–10 each have a written result (pass or fail, plus notes) at the bottom of this file
- [ ] Steps 1, 2 and 4 also done on her reader, with its reserved IP noted
- [ ] These decisions are written down:
  - [ ] which reader is hers, and which is the test reader
  - [ ] `update_mode`: `auto` if steps 5–8 passed, or `side_by_side` if any of them failed
  - [ ] overnight sync: it works, or she opens File Transfer whenever she wants new stories
  - [ ] the `max_image` size for her model (X4 480×800, X3 528×792)

## How to test

The phase is the test. Run `ao3bot push --once` with `host` set to the test reader's IP, using public test works only. Steps 1–3 need no ao3bot code: a browser or `curl` against the reader's web page and API is enough.

## How it fits

Until now everything ran against a fake reader; this checks the fake against the real thing. Phase 9 depends on these results, and phase 10 depends on the overnight answer.

## Watch out for

- **Don't use her login or her list yet.** Use public test works only.
- **If step 5 fails** (no folder with the expected name), don't sink days into it. Set `update_mode = "side_by_side"` for the gift and come back to it in phase 11. One fallback worth trying later is to find the folder by title instead, since each cache folder has a `book.bin` with the title in it.
- **Never replace a test book over USB or by swapping the SD card.** The reader doesn't notice the change and keeps a stale chapter list. Always replace books through the API.
- **Re-run steps 5–8 after any CrossPoint update.** A new firmware version could change the cache.
- **Make sure the reader is actually charging during step 10.** Wi‑Fi left on all night drains the battery.

## Results

| Step | Result | Notes |
|---|---|---|
| 1 Flash | | |
| 2 Network | | |
| 3 API | | |
| 4 Rendering | | |
| 5 Cache hash | | |
| 6 Progress format | | |
| 7 Mode 1 | | |
| 8 Finished book | | |
| 9 Mode 2 cleanup | | |
| 10 Overnight | | |
