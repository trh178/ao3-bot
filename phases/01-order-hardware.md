# Phase 1: Order the hardware

**Where:** you · **Needs:** nothing · **Unblocks:** 7 (the reader) and 8 (the Pi) · **Target:** this week, by Fri Nov 20

## Task

Order the reader and a Pi kit. **The reader is the critical path:** phase 7 needs it in hand by about Nov 30 for a Dec 15 gift.

Shopping list:
- **Reader:** an Xteink X4 or X3 ([product page](https://www.xteink.com/products/Xteink-x4)). Either one works with the design, so pick on stock and price. The X4 is the more common one, and the X3 tilts to turn pages.
- **Pi:** a Raspberry Pi Zero 2 W. A Pi 3, 4 or 5 works just as well if that's what's in stock.
- **Power supply:** the official Raspberry Pi supply for the board you buy. For the Zero 2 W that's 5 V 2.5 A micro‑USB; a Pi 4 or 5 needs USB‑C.
- **microSD card:** 16–32 GB from a name brand, rated A1/A2 or "high endurance".
- **Case:** any case that fits the board.
- **Not needed:** a keyboard, a screen, HDMI adapters or GPIO headers. The Pi runs headless.

## Done when

- [ ] The reader is ordered, with a delivery estimate on or before Nov 30
- [ ] The Pi kit is ordered: board, power supply, microSD card and case
- [ ] Both delivery dates are noted in [00-index.md](00-index.md)
- [ ] If the reader can't arrive by about Dec 1, the gift date has moved to Jan 5

## How to test

- Check the delivery estimates before paying. If no seller can deliver the reader by about Dec 1, plan for Jan 5 now rather than later.
- Each device gets tested the day it arrives: the Pi in phase 8, the reader in phase 7.

## How it fits

Phases 2–6 run on the laptop and need no hardware, so start them while you wait. Phase 7 starts the day the reader arrives, and phase 8 the day the Pi does.

## Watch out for

- **Stock was uneven on Nov 17.** Amazon had listed the X4 at $69, and a copy of Xteink's store showed one colour out of stock until Dec 24. Check Amazon and xteink.com yourself.
- **2.4 GHz only.** The reader (an ESP32‑C3) and the Pi Zero 2 W both use 2.4 GHz Wi‑Fi only. Almost every router has a 2.4 GHz network, but check that yours does.
- **Cheap power supplies and SD cards cause most Pi trouble,** in the form of random crashes and corrupted cards. Spend the extra few dollars.
- **If the Zero 2 W is hard to find,** a Pi 3B+ or 4 is a good substitute. Those also have Ethernet, which is even more reliable when it's plugged into the router.
