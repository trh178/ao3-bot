# Phase 8: Set up the Pi

**Where:** Pi · **Needs:** 1 (the Pi) · **Unblocks:** 9 · **Target:** the day the Pi arrives (it's independent of the software work)

## Task

Get a headless, reliable Pi onto the home Wi‑Fi, ready to run ao3bot.

1. **Flash Raspberry Pi OS Lite (64-bit)** with Raspberry Pi Imager. In Imager's settings, set:
   - the hostname to `ao3bot`
   - your user account
   - your 2.4 GHz Wi‑Fi
   - SSH with your public key
   - your time zone
2. **Boot and update:** run `ssh <user>@ao3bot.local`, then `sudo apt update && sudo apt full-upgrade`.
3. **Router:**
   - Set DHCP reservations for both the Pi and the reader.
   - Make sure both are on the main network, not a guest network.
4. **Install the basics:** `sudo apt install python3-venv sqlite3`.
5. **Create a service user and folders:**
   - a user called `ao3bot`, with no login shell
   - `/opt/ao3bot` for the code and its venv
   - `/etc/ao3bot/` for `config.toml`, owned by `ao3bot` with mode 600
   - `/var/lib/ao3bot` for `state.db`, cookies and the library
6. **Smoke test:**
   - Create the venv with `python3 -m venv /opt/ao3bot/.venv`. Phase 9's systemd unit expects this path.
   - Run `/opt/ao3bot/.venv/bin/pip install fanficfare`.
   - Check that `fanficfare -h` runs.
7. **Cap the logs:** set `SystemMaxUse=50M` in `/etc/systemd/journald.conf` so logs can't fill the card.
8. **Note the Python version** (`python3 --version`) in the Results section below.

## Done when

- [ ] After a power cut (pull the plug, plug it back in), `ssh ao3bot.local` works within 2 minutes, without a keyboard or screen
- [ ] From the Pi, `curl http://<reader-ip>/api/status` returns JSON while the reader is in File Transfer
- [ ] `fanficfare -h` runs inside the venv
- [ ] `vcgencmd get_throttled` prints `throttled=0x0`, meaning no power problems
- [ ] `timedatectl` shows the correct time with "System clock synchronized: yes"

## How to test

The checklist is the test. Repeat the power-cut check after the Pi has been up for a day.

## How it fits

This phase is independent of phases 2–7, so do it whenever the Pi arrives. Phase 9 copies the code onto this box and turns it into a service.

## Watch out for

- **The Zero 2 W only does 2.4 GHz.** If your router uses one network name for both bands, that's usually fine. If it has separate names, use the 2.4 GHz one.
- **Client isolation and guest networks** stop devices on the network from reaching each other, and some mesh systems do it as well. If the Pi can't reach the reader, check this first.
- **`.local` names don't always resolve.** Put the reserved IP addresses in the config, and treat `ao3bot.local` and `crosspoint.local` as conveniences.
- **Use SSH keys, not passwords, and never forward a port to the Pi.** It never needs to be reachable from outside the house.
- **Under-voltage** (`get_throttled` showing anything other than `0x0`) means the power supply is too weak, and over time that corrupts SD cards. Replace the supply.
- **`pip` outside the venv fails on Raspberry Pi OS,** by design. Always use the venv's `pip`.
- **Match the laptop's Python to the Pi's.** If the Pi's Python is older than the laptop's, phase 2's code must not use anything newer than the Pi's version.

## Results

- Pi model:
- OS version:
- Python version:
- Pi IP (reserved):
- Reader IP (reserved):
