# Phase 2: Project skeleton

**Status:** ✅ Done Nov 18. Checked with `python -m ao3bot`; `pip install` hasn't been run yet. · **Where:** laptop · **Needs:** nothing · **Unblocks:** 3, 4, 5 · **Target:** week 1

## Task

Create the `ao3bot` Python package that every later phase plugs into. There's no AO3 or reader code yet.

- **Layout** in the `ao3-bot` folder:
  ```
  ao3bot/
    __init__.py        version
    __main__.py        lets `python -m ao3bot` work
    cli.py             argparse CLI; doctor works, and the rest are stubs naming their phase
    config.py          loads and checks config.toml
    state.py           state.db schema and migrations
    logs.py            logging with the password redacted
                       (later: ao3.py, build.py, push.py, planner.py, web.py)
  tests/               pytest: config, state, CLI, log redaction
  pyproject.toml       dependencies: fanficfare, requests, beautifulsoup4 (pytest for dev)
  config.example.toml  placeholders only
  config.toml          your local copy, never shared (you create it)
  .gitignore           config.toml, data/, *.db, cookies*, library/, .venv/
  README.md            setup and commands
  ```
- **The CLI** has the subcommands `poll`, `build`, `push`, `serve`, `status` and `doctor`. Stubs are fine for now. Use argparse; there's no need for a CLI framework.
- **Config** loads with `tomllib` (in the standard library), with defaults and a clear error for anything missing. The fields are listed in [DESIGN.md](../DESIGN.md) §3.4.
  - `[device] host` is the only required field.
  - Unknown keys are errors, so a typo like `pasword` is caught.
- **`state.db`** (SQLite) holds the tables `works`, `revisions` and `device_files` from DESIGN.md §2. Create them if they're missing.
  - `device_files` records which reader a file went to, because you have two.
- **Logging** never prints the password.
- **`ao3bot doctor`** loads the config, creates the data folder and `state.db`, and prints a short report with the password masked. It makes no network requests.

## Progress

- [x] Files written (Nov 18)
- [x] Checked against the **Done when** list below (Nov 18, Python 3.12.4, pytest 9.0.2). This was run straight from the source folder with `python -m ao3bot`, which needs nothing installed, because the skeleton uses only the standard library.
- [ ] `pip install -e ".[dev]"` in a venv. Do this before phase 3. It adds the `ao3bot` command and installs FanFicFare, both from PyPI, not AO3.

## Done when

- [x] `ao3bot --help` lists the six subcommands
- [x] `ao3bot doctor` with a copy of `config.example.toml` reports OK and creates `state.db`. Running it again is fine, and so is deleting `state.db` first.
- [x] With a broken config, `doctor` says what's wrong in one line. Both cases were checked:
  - a missing `host` gives `[device] host is required`
  - a broken quote gives `not valid TOML: Illegal character '\n' (at line 30, column 15)`
- [x] `pytest` passes: 41 tests in 0.3 s, with no network
- [x] A fake password in the config never shows up in `doctor -v` output

## How to test

1. Set up as in [README.md](../README.md): make a venv, then `pip install -e ".[dev]"`. This step downloads packages from PyPI, but it makes no AO3 requests.
2. `pytest`. **The tests can't reach the network.** An autouse fixture in `tests/conftest.py` blocks every connection except to localhost, so no test can ever call AO3; localhost stays open for phase 5's fake reader. The tests cover:
   - every config error, including that no error ever repeats the password
   - the schema: creating it, reopening it, foreign keys, and refusing a newer schema
   - the CLI: help, doctor, a one-line error for a broken config, the password never printed, and stubs naming their phase
   - log redaction
3. By hand:
   - `copy config.example.toml config.toml`, then `ao3bot doctor`. It should print OK and create `data\state.db`.
   - Delete `host` from `config.toml`, then run `ao3bot doctor`. It should print one line saying `[device] host is required`.
   - Break a quote in `config.toml`. You should get one line with the line number.
   - Delete `data\state.db` and run `doctor` twice. It's recreated the first time, and there are no errors the second time.
   - Put a fake password and a username in `config.toml`, then run `ao3bot doctor`. The password must not appear in the output.

## How it fits

Every later phase is a module inside this package:
- Phase 3 is `ao3.py`.
- Phase 4 is `build.py`.
- Phase 5 is `push.py`.
- Phase 6 is `planner.py`.
- Phase 9 is `serve` and `web.py`.

The same code runs on the laptop now and on the Pi later.

## Watch out for

- **Match the Pi's Python version.** Raspberry Pi OS has its own Python 3; phase 8 records which version. Don't use language features newer than that. 3.11 is the floor, because `tomllib` needs it.
- **Paths.** Use `pathlib` and the configurable `data_dir`. The laptop uses Windows paths, and the Pi uses `/var/lib/ao3bot`. Relative paths in the config are resolved from the config file's folder.
- **Use a virtual environment** (`python -m venv .venv`) on both machines. The Pi's system Python refuses `pip install` outside a venv.
- **Keep dependencies few.** Everything has to install on the Pi as well.
- **Version the schema with `PRAGMA user_version`.** To change the schema, add an entry to `MIGRATIONS` in `state.py`. Never edit an entry that has already run on the Pi.
