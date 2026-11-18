# ao3bot

This bot watches an AO3 **Marked for Later** list and pushes new and updated stories to a CrossPoint e-reader over the home Wi‑Fi. It runs on a Raspberry Pi.

- Design: [DESIGN.md](DESIGN.md)
- Build plan and progress: [phases/00-index.md](phases/00-index.md)

## Set up on a laptop

You need Python 3.11 or newer.

```powershell
# Windows (PowerShell)
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

```bash
# Linux or the Pi
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Then copy `config.example.toml` to `config.toml` and edit the copy. `config.toml` is gitignored. Once her password is in it, it belongs only on the Pi.

## Commands

| Command | What it does | Status |
|---|---|---|
| `ao3bot doctor` | Checks the config and creates `state.db`. Makes no network requests. | ✅ Phase 2 |
| `ao3bot poll [--dry-run]` | Checks the AO3 lists and queues new or updated works | Phase 3, needs AO3 access |
| `ao3bot build <work_id>` | Builds or updates one work's EPUB | Phase 4, needs AO3 access |
| `ao3bot push [--once]` | Uploads new works to the reader, and updates WIPs in place or side by side, keeping her place. Without `--once`, it checks every 60 s. | ✅ Phases 5 and 6 |
| `ao3bot serve` | Runs all of the above in a loop (the Pi service) | Phase 9 |
| `ao3bot status` | Shows the last poll, last push, queue and errors | Phase 9 |

`python -m ao3bot ...` works too, and needs nothing installed for `doctor` and `push`, which use only the standard library.

## Tests

```bash
pytest
```

- **171 tests, about 20 s.** None of them can reach the network: `tests/conftest.py` blocks every connection except localhost.
- **12 tests use the sample EPUBs** in the project root. They're gitignored (`/*.epub`), so copy them along with the folder if you want those tests. Without them, the 12 are skipped.
- **A fake CrossPoint reader** for trying `push` by hand:
  ```bash
  python -m tests.fake_reader --root fake-sd --port 8080
  ```
  Then set `[device] host = "127.0.0.1:8080"`.
