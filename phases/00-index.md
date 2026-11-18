# ao3bot build plan: index

A Raspberry Pi at home watches her AO3 **Marked for Later** list and pushes new and updated stories to her CrossPoint reader over the Wi‑Fi. The design is in [../DESIGN.md](../DESIGN.md). These phase docs are the build plan.

**Gift day:** Tue Dec 15, 2026. **Backup date:** Tue Jan 5, 2027.
**Hardware:** secured, but not delivered yet. That's an Xteink X3, an Xteink X4 and a Raspberry Pi Zero 2 W.

## Where things stand (Nov 18)

- **Done: phases 2, 5 and 6.** `ao3bot doctor` and `ao3bot push` work, including WIP updates that keep her place. 171 tests pass, 12 of them on the sample EPUBs. Everything is committed locally on `main` and has never been pushed.
- **Waiting on AO3 access: phases 3 and 4** (reading her lists, building EPUBs). They need a computer that's allowed to make requests to AO3. Before phase 3, run `pip install -e ".[dev]"` in a venv; it installs FanFicFare.
- **Waiting on hardware:** phase 7 (device tests) needs the readers, and phase 8 (Pi setup) needs the Pi. Phase 7 doesn't need AO3, because the sample EPUBs can stand in for real works.
- **After that:** phase 9 needs phases 3–8, and phase 10 needs phase 9.

## Phases

| # | Phase | Where | Needs | Target | Status |
|---|---|---|---|---|---|
| 1 | [Get the hardware](01-order-hardware.md) | You | nothing | Secured Nov 18 | ◐ waiting on delivery |
| 2 | [Project skeleton](02-project-skeleton.md) | Laptop | nothing | Week 1 | ✅ (pip install still to do) |
| 3 | [Read AO3 lists](03-ao3-lists.md) | Laptop | 2 | Week 1 | ☐ waiting on AO3 access |
| 4 | [Build EPUBs](04-epub-builder.md) | Laptop | 2 | Week 1 | ☐ waiting on AO3 access |
| 5 | [Push to a fake reader](05-push-fake-reader.md) | Laptop | 2 | Week 2 | ✅ |
| 6 | [WIP update planner](06-update-planner.md) | Laptop | 5 | Week 2 | ✅ |
| 7 | [Real device tests](07-device-tests.md) | Laptop + readers | the readers, 5, 6 | As soon as the readers arrive | ☐ waiting on hardware |
| 8 | [Set up the Pi](08-pi-setup.md) | Pi | the Pi | As soon as the Pi arrives | ☐ waiting on hardware |
| 9 | [Run it as a service](09-run-as-service.md) | Pi + reader | 3 to 8 | Week 3 | ☐ |
| 10 | [Soak test and gift day](10-soak-and-gift.md) | Pi + reader | 9 | Week 4 → Dec 15 | ☐ |
| 11 | [Polish](11-polish.md) | Pi | 10 | Dec 15 – Jan 5 (optional) | ☐ |

Each phase doc has the same sections: **Task**, **Done when** (checkboxes), **How to test**, **How it fits**, and **Watch out for**. Tick the boxes as you go, and update the Status column here (☐ not started, ◐ in progress, ✅ done).

## How the phases fit together

```
 Laptop:   2 Skeleton ─┬─► 3 AO3 lists ──────────────────────────────┐
                       ├─► 4 EPUB builder ─┬─► 6 Update planner ─┐   │
                       └─► 5 Fake reader ──┘                     │   │
 Readers:  1 Readers arrive ──────────────────► 7 Device tests ◄─┘   │
                                                      │              │
 Pi:       1 Pi arrives ─────────► 8 Pi setup ─┐      │              │
                                               ▼      ▼              ▼
                                            9 Run as service (needs 3 to 8)
                                                      │
                                                      ▼
                                                10 Soak + gift ─► 11 Polish
```

- **Laptop (2–6):** all the software, built and tested with no hardware. A small fake reader on the laptop stands in for the device.
- **Readers (7):** prove on a real reader what the software assumes about it. This is the go/no-go for in-place updates. The reader that isn't hers is the test reader.
- **Pi (8):** get the Pi on the network. This doesn't depend on any of the software work.
- **Together (9–10):** run everything on the Pi, leave it alone for days, then wrap it.

**The critical path is now the hardware delivery and AO3 access.** Phases 2, 5 and 6 are done. Phase 7 needs the readers, phase 8 needs the Pi, and phases 3 and 4 need a computer that's allowed to make requests to AO3. If the readers can't arrive by about Dec 1, plan for Jan 5.

## What has to be ready for Dec 15

- **Must have:** phases 1–10, with WIP updates working at least in side-by-side mode (`update_mode = "side_by_side"`). That mode is always safe for her place.
- **Nice to have:** in-place updates (`auto`), if phase 7 passes.
- **After the gift:** phase 11.
- **If you're behind:** ship with side-by-side updates, the manual source and a bare status page. Don't skip the soak (phase 10). Move the gift to Jan 5 instead.

## Weekly plan

| Week | Dates | Phases |
|---|---|---|
| 1 | Tue Nov 17 – Mon Nov 23 | Done: 2, 5, 6, and 1 (secured). To do: 3 and 4 on a computer that can reach AO3. |
| 2 | Nov 24 – 30 (Thanksgiving week) | 7 when the readers arrive, 8 when the Pi does |
| 3 | Dec 1 – 7 | 9 |
| 4 | Dec 8 – 14 | 10: soak, welcome batch, wrap it |
| 🎁 | **Tue Dec 15** | Gift day checklist (phase 10) |
| 5–7 | Dec 15 – Jan 5 | 11 (optional) |

## Open decisions

| Decision | Default | Decide in |
|---|---|---|
| Which reader is hers, the X3 or the X4? | The other one becomes the test reader. | Phase 7 |
| Do you have your own AO3 account for testing? | If not, test logged out with the manual source. | Phase 3 |
| Delete old copies automatically after she switches? | Yes, 7 days after she opens the new copy. That's the default now, and `cleanup_old` / `cleanup_grace_days` change it. | Phase 6 (default set) |
| In-place updates on? | `auto` if phase 7 passes, otherwise `side_by_side` | Phase 7 |
| How much of her existing list arrives on gift day? | The newest 10; the rest are marked as seen. | Phase 10 |

## Rules for every phase

- **Read AO3, never write to it.** No kudos, no marks, no bookmarks. Never use `/downloads/`. Keep AO3 requests 5–10 s apart, and back off on errors.
- **Never use her login before gift day.** Everything fetched while logged in as her lands in her AO3 History and spoils the surprise.
- **`config.toml` holds her password.** Keep it out of git, out of logs, out of screenshots, and off the status page.
- **On the reader, touch only `/AO3`** (plus the bot's own position writes under `/.crosspoint`). Replace AO3 books only through the bot, never over USB or by swapping the card.

## Moving to another computer

- Everything lives in this folder: `DESIGN.md`, `phases/`, and the code. Copy the whole `ao3-bot` folder across, including the hidden `.git` folder.
  - The work is committed locally on `main`.
  - The repo has a GitHub remote (`origin`), but nothing has been pushed, so a clone wouldn't have it. Copy the folder rather than cloning.
- **The sample EPUBs are gitignored.** Copy them too if you want the 12 tests that use them. Without them, those tests are skipped.
- Leave `.venv/` behind and rebuild it on the new machine (see README.md). Copy `data/` only if you want to keep its state.
- Once `config.toml` has her password in it, it only needs to live on the Pi. Don't carry it around.
- Claude's memory stays on the old machine. In a new session, point Claude at `phases/00-index.md` and `DESIGN.md`, and say which phase you're on. The design is settled: a Pi at home.
