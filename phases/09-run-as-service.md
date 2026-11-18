# Phase 9: Run it as a service

**Where:** Pi + reader · **Needs:** 3 to 8 · **Unblocks:** 10 · **Target:** week 3 (Dec 1–7)

## Task

Add the `ao3bot serve` command and run it on the Pi under systemd. This is the first time the whole chain runs by itself.

- **`serve` runs these in one process:**
  - every `poll_minutes` (+0–5 min random): poll, then build anything queued, up to 5 per cycle
  - the daily WIP check
  - every 60 s: push, if the reader answers
  - a status page on port 8080, showing the last poll, the last push, the queue, recent errors, the backoff state, and what's on the reader
- **Reuse what's built.** `ao3bot push` already loops every 60 s and calls `push.push_once()`, which returns a `PushResult` with everything the status page needs. `serve` should call the same function.
- **`status`** prints the same information in the terminal.
- **`doctor` on the Pi** checks that the config is OK, that AO3 is reachable, that the reader is reachable (if it's on), the free disk space, and the FanFicFare version.
- **A lock file** makes sure only one copy of `ao3bot` runs at a time.
- **Install:**
  1. Copy the code from the laptop to `/opt/ao3bot`, using scp or rsync.
  2. `pip install` it into the venv.
  3. Put the config at `/etc/ao3bot/config.toml`.
- **The systemd unit, `ao3bot.service`:**
  - `User=ao3bot`
  - `ExecStart=/opt/ao3bot/.venv/bin/ao3bot serve`
  - `Restart=always`, `RestartSec=30`
  - `After=network-online.target` and `Wants=network-online.target`
  - `WantedBy=multi-user.target`
  - logs go to journald

## Done when

- [ ] After `sudo reboot`, the service is running again on its own (`systemctl status ao3bot`)
- [ ] When you add a work ID to the manual list, it's built within one poll cycle, and the status page shows it
- [ ] When you put the reader in File Transfer, the story is in `/AO3` within about a minute and opens on the reader
- [ ] The status page loads from your phone or laptop at `http://ao3bot.local:8080`, or at the Pi's IP
- [ ] An update (made with phase 4's chapter-range trick) arrives in the mode that phase 7 chose

## How to test

Run the checks above with a logged-out config and the manual source. Watch `journalctl -u ao3bot -f` while you do.

## How it fits

This phase joins the software (3–6), the device results (7) and the Pi (8) into the real system. Phase 10 then leaves it alone for days to prove it stays up.

## Watch out for

- **Run one process only.** Two copies would upload everything twice and fight over `state.db`. The lock file prevents this.
- **Keep the status page on the LAN.** Don't forward a port to it, and never show the password or cookies on it.
- **Copy the code, not the config.** The Pi's `config.toml` stays on the Pi, so don't overwrite it when you copy new code across.
- **Memory on a Zero 2 W is 512 MB.** Watch `free -m` during the biggest build. If memory gets tight, skip giant works. Builds already run one at a time.
- **One bad work mustn't stop everything.** It should log an error and move on, not halt deliveries for every other work.
- **Use UTC internally** for anything time-based: backoff, the daily check, and the cleanup grace period.
