# ao3bot build plan: index

A Raspberry Pi at home watches her AO3 **Marked for Later** list and pushes new and updated stories to her CrossPoint reader over the Wi‑Fi. The design is in [../DESIGN.md](../DESIGN.md). These phase docs are the build plan.

**Gift day:** Tue Dec 15, 2026. **Backup date:** Tue Jan 5, 2027, if the reader arrives late.

## Phases

| # | Phase | Where | Needs | Target | Status |
|---|---|---|---|---|---|
| 1 | [Order the hardware](01-order-hardware.md) | You | nothing | by Fri Nov 20 | ☐ |
| 2 | [Project skeleton](02-project-skeleton.md) | Laptop | nothing | Week 1 | ☐ |
| 3 | [Read AO3 lists](03-ao3-lists.md) | Laptop | 2 | Week 1 | ☐ |
| 4 | [Build EPUBs](04-epub-builder.md) | Laptop | 2 | Week 1 | ☐ |
| 5 | [Push to a fake reader](05-push-fake-reader.md) | Laptop | 2 | Week 2 | ☐ |
| 6 | [WIP update planner](06-update-planner.md) | Laptop | 4, 5 | Week 2 | ☐ |
| 7 | [Real device tests](07-device-tests.md) | Laptop + reader | 1, 5, 6 | When the reader arrives (aim for week 2) | ☐ |
| 8 | [Set up the Pi](08-pi-setup.md) | Pi | 1 | When the Pi arrives | ☐ |
| 9 | [Run it as a service](09-run-as-service.md) | Pi + reader | 3 to 8 | Week 3 | ☐ |
| 10 | [Soak test and gift day](10-soak-and-gift.md) | Pi + reader | 9 | Week 4 → Dec 15 | ☐ |
| 11 | [Polish](11-polish.md) | Pi | 10 | Dec 15 – Jan 5 (optional) | ☐ |

Each phase doc has the same sections: **Task**, **Done when** (checkboxes), **How to test**, **How it fits**, and **Watch out for**. Tick the boxes as you go, and update the Status column here.

## How the phases fit together

```
 Laptop:   2 Skeleton ─┬─► 3 AO3 lists ──────────────────────────────┐
                       ├─► 4 EPUB builder ─┬─► 6 Update planner ─┐   │
                       └─► 5 Fake reader ──┘                     │   │
 Reader:   1 Order ─ reader arrives ──────────► 7 Device tests ◄─┘   │
                                                      │              │
 Pi:       1 Order ─ Pi arrives ─► 8 Pi setup ─┐      │              │
                                               ▼      ▼              ▼
                                            9 Run as service (needs 3 to 8)
                                                      │
                                                      ▼
                                                10 Soak + gift ─► 11 Polish
```

- **Laptop (2–6):** all the software, built and tested with no hardware. A small fake reader on the laptop stands in for the device.
- **Reader (7):** prove on the real reader what the software assumes about it. This is the go/no-go for in-place updates.
- **Pi (8):** get the Pi on the network. This doesn't depend on any of the software work.
- **Together (9–10):** run everything on the Pi, leave it alone for days, then wrap it.

**The critical path is the reader.** Phase 7 needs it in hand by about Nov 30.

## What has to be ready for Dec 15

- **Must have:** phases 1–10, with WIP updates working at least in side-by-side mode (`update_mode = "side_by_side"`). That mode is always safe for her place.
- **Nice to have:** in-place updates (`auto`), if phase 7 passes.
- **After the gift:** phase 11.
- **If you're behind:** ship with side-by-side updates, the manual source and a bare status page. Don't skip the soak (phase 10). Move the gift to Jan 5 instead.

## Weekly plan

| Week | Dates | Phases |
|---|---|---|
| 1 | Tue Nov 17 – Mon Nov 23 | 1 (order today), 2, 3, 4 |
| 2 | Nov 24 – 30 (Thanksgiving week) | 5, 6. The reader arrives → 7. The Pi arrives → 8. |
| 3 | Dec 1 – 7 | 9 |
| 4 | Dec 8 – 14 | 10: soak, welcome batch, wrap it |
| 🎁 | **Tue Dec 15** | Gift day checklist (phase 10) |
| 5–7 | Dec 15 – Jan 5 | 11 (optional) |

## Open decisions

| Decision | Default | Decide in |
|---|---|---|
| X3 or X4? | Whichever is in stock. The X4 is the more common one. | Phase 1 |
| Do you have your own AO3 account for testing? | If not, test logged out with the manual source. | Phase 3 |
| Delete old copies automatically after she switches? | Yes, 7 days after she opens the new copy | Phase 6 |
| In-place updates on? | `auto` if phase 7 passes, otherwise `side_by_side` | Phase 7 |
| How much of her existing list arrives on gift day? | The newest 10; the rest are marked as seen. | Phase 10 |

## Rules for every phase

- **Read AO3, never write to it.** No kudos, no marks, no bookmarks. Never use `/downloads/`. Keep AO3 requests 5–10 s apart, and back off on errors.
- **Never use her login before gift day.** Everything fetched while logged in as her lands in her AO3 History and spoils the surprise.
- **`config.toml` holds her password.** Keep it out of git, out of logs, out of screenshots, and off the status page.
- **On the reader, touch only `/AO3`** (plus the bot's own position writes under `/.crosspoint`). Replace AO3 books only through the bot, never over USB or by swapping the card.

## Moving to another computer

- Everything lives in this folder: `DESIGN.md`, `phases/`, and the code once it exists. Copy the whole `ao3-bot` folder across. Nothing is in git or the cloud.
- Once `config.toml` has her password in it, it only needs to live on the Pi. Don't carry it around.
- Claude's memory stays on the old machine. In a new session, point Claude at `phases/00-index.md` and `DESIGN.md`, and say which phase you're on. The design is settled: a Pi at home.
