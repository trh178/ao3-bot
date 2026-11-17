# Phase 11: Polish (after the gift)

**Where:** Pi · **Needs:** 10 · **Target:** Dec 15 – Jan 5, all optional

## Task

Work through the list one item at a time. Each item stands on its own. If in-place updates are still off after phase 7, do that item first.

| Item | What it involves |
|---|---|
| **In-place updates** (if phase 7 forced side-by-side) | Fix the cache-folder lookup and pass phase 7's steps 5–8 again |
| **LAN OPDS feed** | `/opds` on the Pi, listing only works that aren't on the reader yet. A backup way for her to pull a story without File Transfer. |
| **Alerts to you** | One message (ntfy, Pushover or email) after repeated failures |
| **Weekly backup** | Copy `state.db` and the library to your laptop or a NAS automatically |
| **Bookmarks as a second source** | Turn it on if she bookmarks things she wants to read |
| **A firmware update routine** | Before updating CrossPoint, back up. After updating, re-run phase 7's steps 5–8. |

## Done when

- [ ] In-place updates: phase 7's steps 5–8 pass, and `update_mode = "auto"`
- [ ] OPDS: she can pull a new story from the reader's OPDS browser without opening File Transfer
- [ ] Alerts: a forced failure sends one message, not a flood
- [ ] Backup: a fresh backup appears each week without you doing anything
- [ ] Bookmarks: a new bookmark arrives the same way a Mark for Later does
- [ ] Firmware routine: written down as a short checklist at the bottom of this file

## How to test

Each checkbox is its own test. After any change, re-run the phase 9 checks.

## How it fits

None of this is needed for the gift. Every item here is a change to a system that already works.

## Watch out for

- **OPDS re-downloads wipe her place.** That's why the feed lists only works that aren't on the reader yet; updates always go through the push.
- **OPDS filenames:** the reader names a download `Author - Title.epub`, based on the feed entry. Title each feed entry `Title [id]` so that pulled files match the pushed naming, and set the reader's OPDS download folder to `/AO3`.
- **Alerts send data off your network.** Keep them to messages like "ao3bot: 3 polls failed", with nothing about her or what she's reading.
- **Every change risks breaking a working gift.** Test on the laptop against the fake reader first, then copy to the Pi.
