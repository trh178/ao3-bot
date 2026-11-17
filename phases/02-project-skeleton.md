# Phase 2: Project skeleton

**Where:** laptop · **Needs:** nothing · **Unblocks:** 3, 4, 5 · **Target:** week 1

## Task

Create the `ao3bot` Python package that every later phase plugs into. There's no AO3 or reader code yet.

- **Layout** in the `ao3-bot` folder:
  ```
  ao3bot/              the package: cli.py, config.py, state.py
                       (later: ao3.py, build.py, push.py, planner.py, web.py)
  tests/               pytest
  pyproject.toml       dependencies: fanficfare, requests, beautifulsoup4
  config.example.toml  placeholders only
  config.toml          your local copy, never shared
  .gitignore           config.toml, *.db, cookies*, library/, .venv/
  ```
- **The CLI** has the subcommands `poll`, `build`, `push`, `serve`, `status` and `doctor`. Stubs are fine for now. Use argparse; there's no need for a CLI framework.
- **Config** loads with `tomllib` (in the standard library), with defaults and a clear error for anything missing. The fields are listed in [DESIGN.md](../DESIGN.md) §3.4.
- **`state.db`** (SQLite) holds the tables `works`, `revisions` and `device_files` from DESIGN.md §2. Create them if they're missing.
- **Logging** never prints the password.
- **`ao3bot doctor`** loads the config, creates the data folder and `state.db`, and prints a short report with the password masked.

## Done when

- [ ] `ao3bot --help` lists the six subcommands
- [ ] `ao3bot doctor` with a copy of `config.example.toml` reports OK and creates `state.db`
- [ ] With a broken config (a missing field, or a TOML syntax error), `doctor` says what's wrong in one line
- [ ] `pytest` runs and passes, with at least one config test and one state test

## How to test

- Run `doctor` against a good config, one with a missing field, and one with a syntax error.
- Delete `state.db` and run `doctor` again: the tables come back. Run it a second time: there are no errors.
- Put a fake password in the config, run every command, and search the output for it. There should be no matches.

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
- **Paths.** Use `pathlib` and the configurable `data_dir`. The laptop uses Windows paths, and the Pi uses `/var/lib/ao3bot`.
- **Use a virtual environment** (`python -m venv .venv`) on both machines. The Pi's system Python refuses `pip install` outside a venv.
- **Keep dependencies few.** Everything has to install on the Pi as well.
- **Version the schema with `PRAGMA user_version`,** so later phases can add columns without editing the database by hand.
