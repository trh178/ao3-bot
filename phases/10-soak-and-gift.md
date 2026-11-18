# Phase 10: Soak test and gift day

**Where:** Pi + reader · **Needs:** 9 · **Unblocks:** the gift · **Target:** Dec 8–14, with the gift on Tue Dec 15

## Task

Leave the system running for at least 5 days without touching it, and break it on purpose a few times. Then load a welcome batch and wrap the reader. On gift day, switch the bot to her account.

**Soak (Dec 8–13)**
- Keep the bot running on the manual source, logged out (or on your own account), pushing to the **test reader**.
- Add a work or two each day, including a couple of active public WIPs so that real updates come through.
- Break it on purpose, once each:
  - pull the Pi's power during a build
  - take the reader out of File Transfer during an upload
  - unplug the internet for an hour, so AO3 can't be reached
  - restart the router
- Back up `state.db` and the library to your laptop.

**Welcome batch (Dec 13–14)**
- Switch `[device]` to **her reader**: set `host` to its reserved IP, `name` to something like `"her-x3"`, and `max_image` to its screen size. Restart the service.
- Put the stories you want her to find on day one into the manual list.
- Let them sync, then open each one on the reader.
- Wrap it.

**Gift day checklist (Dec 15)**
1. She changes her AO3 password, which AO3 recommends after the Oct 29 incident.
2. She checks that **History** is turned on in her AO3 preferences. Marked for Later needs it.
3. You edit `/etc/ao3bot/config.toml`:
   - Add her username and new password.
   - Set `sources = ["marked_for_later"]`, and add `"bookmarks"` if she wants it.
   - Set `backfill_newest`.
4. Run `sudo systemctl restart ao3bot`, then `ao3bot doctor`. It should log in and show her list.
5. Show her the two habits: **Mark for Later** on AO3, and **File Transfer** when the reader goes on the charger.
6. She marks a story, and you both watch it arrive.

## Done when

- [ ] 5 days in a row with no manual fixes
- [ ] Each break-it test recovered by itself, or you fixed the code and ran that test again
- [ ] A backup is on your laptop
- [ ] The welcome batch is on the reader and every story opens
- [ ] On gift day, her first Mark for Later arrives on the reader

## How to test

The soak is the test. Check the status page once a day, and don't touch anything that isn't broken. If you have to fix something late in the week, keep the soak running through Dec 14.

## How it fits

This is the last step before the gift. Everything after it is optional (phase 11).

## Watch out for

- **Her login stays out of the config until gift day.** Using it earlier puts bot visits in her History.
- **Tell her** that the bot's visits show up in her AO3 History, and that this is normal.
- **Decide the backfill.** Her Marked for Later list may already be long. `backfill_newest` (10 by default) sets how many existing entries arrive on day one, and the rest are marked as seen. Decide whether she'd rather have all of them.
- **The Marked for Later parser gets its first real test on gift day** if you had no AO3 account of your own (phase 3). Compare `doctor`'s output with her actual list.
- **Tell her that deleting AO3 books on the reader is fine, but replacing them over USB isn't.**
- **Don't cut the soak short.** If phases 7–9 slip, move the gift to Jan 5 instead.
