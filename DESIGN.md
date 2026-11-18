# AO3 → CrossPoint Auto-Delivery: Design

**Decision:** a Raspberry Pi at home, on the same Wi‑Fi as the reader. It watches her AO3 list and pushes EPUBs to the reader over the local network.
**Build plan:** [phases/00-index.md](phases/00-index.md)
**Gift date:** Tue Dec 15, 2026 (backup: Tue Jan 5, 2027)
**Hardware (in hand):** an Xteink X3 and an Xteink X4, both running [CrossPoint Reader](https://github.com/crosspoint-reader/crosspoint-reader) 2.0.x. One is hers and the other is the test reader. Plus a Raspberry Pi Zero 2 W.

---

## Summary

- **Trigger:** she taps **Mark for Later** on a work on AO3.
- **The Pi** checks her Marked for Later list every ~30 minutes (logged in as her) and builds an EPUB of anything new or updated with FanFicFare.
- **Delivery:** whenever the reader is on *File Transfer → Join Network*, the Pi uploads new and updated stories into `/AO3` through the reader's local web API. The habit: File Transfer on when it goes on the charger at night.
- **WIP updates keep her place.** Before replacing a book, the Pi reads her saved position off the reader, and it writes it back afterwards. If it can't place her with certainty, it puts the new copy next to the old one, and it deletes the old one after she has switched.
- **Her login** lives in a config file on the Pi. AO3 has no API and no OAuth.
- **The bot only reads AO3.** It never leaves kudos, bookmarks anything, or marks anything as read.

---

## 1. How it works

```
 She, on AO3 (phone or laptop)          Pi (ao3bot)                           Reader (CrossPoint)
 ─────────────────────────────          ───────────                           ───────────────────
 taps "Mark for Later" on a work ──►  every ~30 min: reads her Marked
                                      for Later list (logged in as her)
                                      → new or updated work → FanFicFare
                                        builds an EPUB → local library
                                                                       ◄── she opens File Transfer →
                                                                           Join Network (or leaves it on
                                      every 60 s: "is the reader up?"          while charging overnight)
                                      → yes → lists /AO3 → uploads new
                                        and updated EPUBs ───────────────────►  files land in /AO3
                                                                       ◄── she exits File Transfer;
                                                                           new stories are in the Library
```

She does two things: she taps *Mark for Later*, and she opens File Transfer (or leaves it on overnight). There's nothing to do on the reader for each story.

---

## 2. Components

```
┌──────────────────────────────────────── HOME WI-FI (2.4 GHz) ────────────────────────────────────────┐
│                                                                                                      │
│  Raspberry Pi Zero 2 W  ── ao3bot (one Python package, one systemd service)                          │
│  ┌──────────────────────────────────────────────────────────────────────────────┐                    │
│  │ poller   every 30 min ±jitter: log in (saved cookie), read lists, diff state  ├── HTTPS ──────────►│──► archiveofourown.org
│  │          daily: re-check unfinished WIPs already delivered                    │                    │
│  │ builder  FanFicFare (update mode for WIPs, images shrunk)                     │                    │
│  │          → <data_dir>/library/<work_id>/rev-<n>.epub                          │                    │
│  │ state    SQLite state.db: works, revisions, what's on the reader              │                    │
│  │ pusher   every 60 s: GET /api/status → list /AO3 → upload → updates (§5)      │                    │
│  │ web      http://ao3bot.local:8080 status page (for you)                       │                    │
│  └───────────────────────────────┬──────────────────────────────────────────────┘                    │
│                                  │ HTTP, LAN only (the reader has no auth)                           │
│                                  ▼                                                                   │
│  CrossPoint reader in File Transfer → Join Network (DHCP-reserved IP, also crosspoint.local)         │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Piece | What it is | Notes |
|---|---|---|
| Hardware | Raspberry Pi Zero 2 W, with a 5 V 2.5 A micro‑USB supply and a good 16–32 GB microSD card | It draws about 1 W. |
| OS | Raspberry Pi OS Lite (64-bit), headless, reached over SSH | |
| `ao3bot` | One Python 3.11+ package with the subcommands `poll`, `build`, `push`, `serve`, `status` and `doctor` | It's developed and tested on the laptop, then copied to the Pi. |
| FanFicFare | A pip dependency, called through its CLI | It builds from `/works/<id>?view_full_work=true`. `-u` adds only the new chapters. |
| State | SQLite `state.db` | `works` (id, title, authors, chapters, complete, ao3_updated, sources, first_seen, last_checked); `revisions` (work_id, rev, chapters, sha256, chapter_hashes, built_at); `device_files` (device, work_id, rev, path, delivered_at, superseded_at) |
| Library | `<data_dir>/library/<work_id>/rev-<n>.epub` | It keeps the last 3 revisions of each work, and doubles as a backup of what's on the reader. |
| Service | One systemd service running `ao3bot serve` | `Restart=always`. Logs go to journald. |
| Status page | `http://ao3bot.local:8080` | It's for you, on the LAN only. She never needs to know the Pi exists. |
| Network | DHCP reservations for the Pi and the reader | Both must be on the same 2.4 GHz network, not a guest network, with no client isolation. |

---

## 3. AO3: sources, login, polling

### 3.1 Facts the design rests on

| Fact | What it means here |
|---|---|
| AO3 has no favorites or stars. It has Kudos, Bookmarks, Subscriptions (email only), and **Marked for Later**. | Marked for Later is the trigger. |
| Marked for Later lives at `/users/<her>/readings?show=to-read`. It needs **her login** and **History turned on**, and it's sorted by *last viewed*, 20 per page. A work leaves the list only through "Mark as Read" or deleting it from History. (Confirmed in [AO3's source](https://github.com/otwcode/otwarchive/blob/master/app/controllers/readings_controller.rb).) | Compare work IDs, not list positions, because just viewing a work moves it up. |
| Every work opened while logged in goes into her History. | The bot's visits show up there. **Don't use her login before gift day.** |
| There's no API, no webhooks, and no feed of a user's lists. | Poll the HTML pages, and keep all parsing in one file. |
| Restricted works need a login. Adult works need a confirmation (`view_adult=true`). | Her login, plus `adult_ok = true`. |
| `robots.txt` disallows `/downloads/` and allows `/users/` and `/works/<id>`. The Downloads FAQ allows scripts. The ToS bans commercial scraping and disrupting the site. | FanFicFare never touches `/downloads/`. Stay low-volume and read-only. |
| Cloudflare sits in front, with per-IP limits. | A home IP, plus backoff. |
| AO3 has been degraded since the Oct 29, 2026 incident. It came back Nov 15 with HTML-only downloads and no new accounts, and OTW recommends that everyone change their password. | Don't depend on AO3's own downloads. She changes her password before it goes into the config. |

### 3.2 Sources

| Source | URL | Login | Use |
|---|---|---|---|
| `marked_for_later` | `/users/<username>/readings?show=to-read` | Required (hers), with History on | **The primary source, from gift day on** |
| `bookmarks` | `/users/<username>/bookmarks` | Optional (public bookmarks only without it) | An optional second source, if she bookmarks things she wants to read |
| `manual` | A local text file of work IDs or URLs | None | Testing, and the welcome batch |

The bot uses every enabled source combined.

### 3.3 Poll logic

```text
every poll_minutes (+0–5 min random):
  if backoff is active: skip
  session = load_cookie_or_login()                  # logs in only when the cookie has expired
  for source in enabled sources:
     for page in 1..3:                              # stop early once a page has nothing new
        for blurb in parse(GET source page):        # work_id, title, authors, chapters "x/y", updated
           unknown work_id                → queue build "new"
           chapters or updated changed    → queue build "update"
  daily: each delivered work that's unfinished and not on any list any more
           → GET /works/<id> once → queue a build if it changed
           (stop tracking once it's complete, or after 12 months with no update)
  first time a source is seen: queue the newest `backfill_newest`, mark the rest seen
  build up to 5 per cycle, 5–10 s between AO3 requests
  on 429 / 503 / 525 / a Cloudflare challenge / an unexpected login page:
           back off 1 h, doubling up to 24 h
```

### 3.4 Config

On the Pi the config lives at `/etc/ao3bot/config.toml`, owned by the service user, with mode 600. It's never committed or shared. Ship a `config.example.toml` with placeholders.

```toml
[ao3]
username        = ""                       # empty = logged out (testing). Hers from gift day.
password        = ""                       # she changes it first (post-incident advice)
sources         = ["manual"]               # gift day: ["marked_for_later"], plus "bookmarks" if wanted
manual_ids_file = "ids.txt"
poll_minutes    = 30
adult_ok        = true
backfill_newest = 10                       # how many existing entries a new source delivers
user_agent      = "ao3bot/0.1 (personal e-reader sync, one user)"

[device]
host               = "192.168.1.50"        # the reader's DHCP-reserved IP
name               = "test-x4"             # label in state.db (defaults to host); "her-x3" etc. from phase 10
folder             = "/AO3"
update_mode        = "auto"                # auto | in_place | side_by_side (§5)
cleanup_old        = "after_switch"        # after_switch | manual
cleanup_grace_days = 7

[epub]
max_image = "480x800"                      # X3: 528x792

[paths]
data_dir = "/var/lib/ao3bot"               # state.db, cookies, library/
```

**Sessions:** the bot saves the cookie jar after each login and reuses it, so it logs in again only when AO3 has expired the session. FanFicFare gets the same credentials through its own `personal.ini` and logs in only when a work needs it.

**Before gift day:** test logged out with the `manual` source, or with your own AO3 account if you have one. On gift day she changes her password and turns History on, and her login goes into the config.

---

## 4. Delivery to the reader

### 4.1 Reader facts

- The web server runs **only** while she's on the **File Transfer** screen (Join Network or Hotspot) or in Calibre Wireless mode.
- It's reachable on the LAN only, with **no auth**. It answers at the reader's IP, and also at `crosspoint.local`.
- **API:**
  - `GET /api/status`
  - `GET /api/files?path=`
  - `POST /upload?path=` (multipart field `file`; `overwrite=1` replaces an existing file)
  - `GET /download?path=`
  - `POST /mkdir`, `/move`, `/rename` and `/delete`

  Uploading a file clears the reader's caches for that path, and the Library picks the new file up the next time it opens.
- It reads EPUB 2 and 3, with about 380 KB of usable RAM. Large images are slow, so shrink them to the screen size (X4 480×800, X3 528×792).

### 4.2 Push logic

```text
every 60 s:
  GET http://<host>/api/status (2 s timeout); no answer → the reader isn't in File Transfer; wait
  make /AO3 if it's missing; list it
  for each work whose latest revision isn't on the reader:
      new work   → POST /upload?path=/AO3  (file = "Author - Title [work_id].epub")
      update     → the update strategy (§5)
      re-list, check the name and size → mark delivered in state.db
  one upload at a time; stop cleanly if the reader disappears (she left the screen)
```

### 4.3 Rules

- **Filenames** follow `Author - Title [work_id].epub`.
  - Replace `/\:*?"<>|` with `_`, trim trailing dots and spaces, and cap the name at 100 bytes (not characters).
  - The `[work_id]` keeps names unique and maps files back to works.
- **Use exactly the same path string every time.** The reader keys her position on the exact path, case included.
- **Never touch anything the bot didn't put there,** and never work outside `/AO3`. The one exception is the bot's own progress writes under `/.crosspoint` (§5).
- **Never rename a book she may have opened.** To the reader, a renamed file is a new book with no position.
- **Replace AO3 books only through the bot, never over USB or by swapping the card.** The reader doesn't notice a changed file and keeps a stale chapter list. "Delete Book Cache" in the reader's menu fixes that if it happens.

---

## 5. WIP updates: keeping her place

### 5.1 How CrossPoint stores her position

This comes from CrossPoint's source; release 2.0.0 has the same logic as `develop`.

- **The position file** is `/.crosspoint/epub_<hash>/progress.bin`.
  - `<hash>` is `std::hash<std::string>` of the book's **full SD path**, for example `/AO3/Author - Title [123].epub`. On the reader's 32-bit chip this is libstdc++'s MurmurHash2 with seed `0xc70f6907`, written in decimal. **This is not yet verified on a device.**
- **The format** is little-endian: `u16` chapter (spine index), `u16` page, `u16` page count, then an optional `u32` character offset within the chapter. When a book opens, the character offset wins over the page number, so her place survives re-pagination.
- **Any network replace wipes her position.** That covers web upload (with or without `overwrite`), WebDAV PUT and OPDS re-download. Each one deletes the whole `epub_<hash>` folder, and the book then opens at the start. Bookmarks and the recent-books list survive.
- **The HTTP API can read and write `/.crosspoint`.** `GET /download` reads `progress.bin`, and `POST /mkdir` plus `POST /upload` write it back. (WebDAV blocks paths that start with a dot.)
- **The reader records what she opened.** `/.crosspoint/recent.json` lists the last 10 books she opened.

### 5.2 Mode 1: update in place and keep her spot

```text
P    = exact device path, e.g. "/AO3/Author - Title [123].epub"
dir  = "/.crosspoint/epub_" + cphash(P)
prog = GET /download?path=<dir>/progress.bin
if 404:                                   # never opened: nothing to lose
    POST /upload?path=/AO3&overwrite=1 ; done
pos = parse(prog)
if pos.spine >= old_rev.spine_count:      # she had finished it
    new_pos = start of the first new chapter
else:
    i = index in new_rev of the chapter whose text hash matches old_rev.spine[pos.spine]
    if not found: → Mode 2
    new_pos = (i, pos.page, pos.pages, pos.char_offset)
POST /upload?path=/AO3&overwrite=1        # the firmware wipes <dir>
POST /mkdir  → <dir>
POST /upload → <dir>/progress.bin = new_pos
read it back; if it doesn't match, flag "position lost" on the status page
```

- FanFicFare's update mode keeps the existing chapters and appends the new ones, so unchanged chapters hash the same.
- Turn off FanFicFare's update log page so the front matter stays stable.
- Hash **chapter text**, not whole files. The title page changes on every build.
- She's on the File Transfer screen while the bot works, so her position can't change mid-update.

### 5.3 Mode 2: side by side, then clean up

The bot uses Mode 2 whenever Mode 1 isn't certain:

1. Upload the new revision **next to** the old one, as `Author - Title [123] (ch 14).epub`. The old copy and her place in it stay untouched.
2. Seed the new copy with a best-guess position (the same chapter, if it can be found).
3. **Cleanup** (`after_switch`): once `recent.json` shows she has opened the new copy and `cleanup_grace_days` have passed, `POST /delete` the old copy. With `manual`, she deletes old copies on the reader herself (long-press, then Delete).
4. Never delete the book she opened most recently.

### 5.4 `update_mode = "auto"`

Mode 1 runs only when everything checks out. The bot falls back to Mode 2 in any of these cases:
- `progress.bin` isn't 4, 6 or 10 bytes long,
- there's no cache folder for a book she has opened,
- her chapter's hash isn't in the new revision.

**The rule: an update never costs her place.** At worst, she has two copies of a book for a while.

---

## 6. Still to verify

| What | Checked in |
|---|---|
| The cache folder name (`cphash`) on a real reader | Phase 7 |
| That File Transfer stays up overnight on the charger | Phase 7 |
| That `recent.json` updates when she opens a book | Phase 7 |
| The exact web API parameter names | Phase 5 (from the docs), Phase 7 (on the device) |
| FanFicFare's option names (adult confirmation, image size, update log page) and its `URL[1-3]` chapter range from the CLI | Phase 4 |
| The markup of the Marked for Later page | Phase 3, or on gift day if you have no AO3 account of your own |

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| AO3 markup changes and breaks the parser | All parsing lives in one file. Keep FanFicFare updated and watch the status page. |
| AO3 is down or degraded | Backoff. The library keeps everything already built. |
| AO3 flags the account for automated use | A home IP, about 50–100 requests a day, cookie reuse, an honest user agent, and no writes to AO3 |
| Her History fills with bot visits | It's harmless. Tell her. Never use her login before gift day. |
| An update loses her place | Mode 1 carries her position across; `auto` falls back to side by side whenever it isn't sure. |
| A firmware update changes the cache format | The bot sanity-checks the cache and drops to Mode 2. Re-run the phase 7 device tests after any CrossPoint update. |
| File Transfer sleeps overnight | She opens File Transfer for a minute when she wants new stories. |
| The Pi's SD card dies or power is bad | A good power supply and card. Back up `state.db` and the library weekly. |
| The config file leaks | Mode 600, never committed, the password never logged, and a fresh AO3 password |

---

## Sources (read 2026-11-17)

**CrossPoint**
- README: https://github.com/crosspoint-reader/crosspoint-reader
- Web server: https://github.com/crosspoint-reader/crosspoint-reader/blob/develop/docs/webserver.md
- HTTP endpoints: https://github.com/crosspoint-reader/crosspoint-reader/blob/develop/docs/webserver-endpoints.md
- User guide: https://github.com/crosspoint-reader/crosspoint-reader/blob/develop/USER_GUIDE.md
- Source files read for §5 (on `develop`):
  - `lib/Epub/Epub.cpp`
  - `src/activities/reader/EpubReaderUtils.h`
  - `src/activities/reader/EpubReaderActivity.cpp`
  - `src/network/CrossPointWebServer.cpp`
  - `src/network/ProtectedPaths.h`
  - `src/util/OpdsFilename.cpp`
  - `src/RecentBooksStore.cpp`
  - `src/activities/home/FileBrowserActivity.cpp`

**AO3 / OTW**
- Terms of Service: https://archiveofourown.org/tos
- robots.txt: https://archiveofourown.org/robots.txt
- Downloads FAQ: https://archiveofourown.org/faq/downloading-fanworks
- History and Mark for Later FAQ: https://archiveofourown.org/faq/history-and-mark-for-later
- Readings controller: https://github.com/otwcode/otwarchive/blob/master/app/controllers/readings_controller.rb
- Incident status: https://www.otwstatus.org/incidents/g12jnxck9g6h

**FanFicFare**
- README: https://github.com/JimmXinu/FanFicFare
- CLI options: https://github.com/JimmXinu/FanFicFare/blob/main/fanficfare/cli.py
- AO3 adapter: https://github.com/JimmXinu/FanFicFare/blob/main/fanficfare/adapters/base_otw_adapter.py
