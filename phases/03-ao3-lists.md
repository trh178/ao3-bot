# Phase 3: Read AO3 lists

**Where:** laptop · **Needs:** 2 · **Unblocks:** 9 · **Target:** week 1

## Task

Write `ao3.py` and the `poll` command. They find works that are new or updated on the enabled sources and queue them for building. The logic is in [DESIGN.md](../DESIGN.md) §3.3.

- **HTTP client:**
  - one session, the honest user agent from the config, 5–10 s between requests, and a 30 s timeout
  - on a 429, 503 or 525, a Cloudflare challenge page, or an unexpected login page: stop and back off for 1 h, doubling up to 24 h. Save the backoff in `state.db`.
- **Login,** only if `username` is set:
  - Get a token from `GET /token_dispenser.json`, then `POST /users/login` with remember-me.
  - Save the cookie jar in `data_dir`, and reuse it.
  - Log in again only when a page shows you're logged out, and at most once per cycle.
- **Sources:**
  - `manual`: work IDs or URLs in a text file, one per line. It's for testing and the welcome batch.
  - `marked_for_later`: `/users/<username>/readings?show=to-read`. It needs a login and History turned on.
  - `bookmarks`: `/users/<username>/bookmarks`. Without a login it shows public bookmarks only.
- **Parser:** from each work blurb, take the work ID, title, authors, chapters (`x/y` or `x/?`) and updated date. Read up to 3 pages, and stop early when a page has nothing new.
- **Diff:**
  - an unknown work ID → queue it as "new"
  - a changed chapter count or updated date → queue it as "update"
  - compare IDs, never list positions
- **Daily WIP check:** for delivered works that are unfinished and on no list any more, fetch `/works/<id>` once a day. Stop once the work is complete, or after 12 months with no update.
- **Backfill:** the first time a source is seen, queue only the newest `backfill_newest` (10 by default) and mark the rest as seen.
- **`ao3bot poll --dry-run`** prints what it would queue and changes nothing.

## Done when

- [ ] Parser tests pass on saved HTML pages:
  - a bookmarks page
  - a work page
  - a page with a deleted, hidden, series or external item
  - a Marked for Later page, if you can get one
- [ ] `poll --dry-run` with the manual source and 3–5 public work IDs prints the right titles and chapter counts
- [ ] Running `poll` twice with nothing changed queues nothing the second time
- [ ] Changing a stored chapter count in `state.db` makes the next poll queue an "update"
- [ ] A faked 429 response causes a backoff that's recorded, and the next run exits early
- [ ] With a username set (yours, never hers), the first run logs in and the next run reuses the cookie without logging in again

## How to test

- **Fixture tests.** Save pages from your browser into `tests/fixtures/`, logged out, and write the parser tests against them. Those tests never touch AO3.
- **Backoff and login-page detection.** Test these with mocked responses, not the real site.
- **Live checks.** Keep them to a handful of requests, logged out, against public works.

## How it fits

This phase produces the queue of work IDs that phase 4 builds. On the Pi in phase 9, it runs every 30 minutes.

## Watch out for

- **Never use her login before gift day.** Every work fetched while logged in shows up in her History. Use the manual source logged out, or your own account if you have one. AO3 isn't creating new accounts right now.
- **With no account of your own, the Marked for Later parser can't be checked live until gift day.** Make it look for the same work-blurb structure as the bookmarks page. Also make `doctor` print what it found, so you can compare it with her real list on gift day (phase 10).
- **Bookmarks aren't always works.** Some are series or external works; skip those. Skip deleted, hidden and "mystery" works too.
- **Restricted works are invisible without a login.** That's expected.
- **AO3 is still degraded after the Oct 29 incident.** Expect errors and slow pages. The backoff is not optional.
- **Read-only.** The login is the only POST. Never touch `/downloads/`.
- **Keep all HTML parsing in one file.** When AO3 changes its markup, the fix is then confined to that one file.
