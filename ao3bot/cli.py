"""The `ao3bot` command."""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import stat
import sys
import time
from contextlib import closing

from . import __version__
from .config import Config, ConfigError, find_config_path, load_config
from .logs import setup_logging
from .push import PushResult, push_once
from .state import StateError, open_db, row_counts, schema_version

log = logging.getLogger("ao3bot")

# Commands that later phases fill in: name -> (help text, phase that builds it)
PLANNED = {
    "poll": ("check AO3 lists and queue new or updated works", 3),
    "build": ("build or update one work's EPUB", 4),
    "serve": ("run poll, build and push in a loop (the Pi service)", 9),
    "status": ("show the last poll, last push, queue and errors", 9),
}
MIN_PUSH_INTERVAL = 10


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ao3bot",
        description="Deliver AO3 stories to a CrossPoint e-reader.",
    )
    parser.add_argument("--version", action="version", version=f"ao3bot {__version__}")
    parser.add_argument(
        "-c", "--config",
        help="path to config.toml (default: $AO3BOT_CONFIG, then ./config.toml, then /etc/ao3bot/config.toml)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    p = sub.add_parser("poll", help=PLANNED["poll"][0])
    p.add_argument("--dry-run", action="store_true", help="print what would be queued, and change nothing")

    p = sub.add_parser("build", help=PLANNED["build"][0])
    p.add_argument("work_id", type=int, help="the AO3 work ID")

    p = sub.add_parser("push", help="upload new and updated EPUBs to the reader")
    p.add_argument("--once", action="store_true", help="push once and exit (default: keep checking for the reader)")
    p.add_argument("--interval", type=int, default=60, help="seconds between checks without --once (default 60)")

    sub.add_parser("serve", help=PLANNED["serve"][0])
    sub.add_parser("status", help=PLANNED["status"][0])
    sub.add_parser("doctor", help="check the config and state.db (makes no network requests)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)
    if args.command == "doctor":
        return doctor(args)
    if args.command == "push":
        return push(args)
    _, phase = PLANNED[args.command]
    print(f"ao3bot {args.command}: not built yet (phase {phase})", file=sys.stderr)
    return 2


def load(args: argparse.Namespace) -> Config:
    """Find and load the config, then restart logging so the password is redacted."""
    cfg = load_config(find_config_path(args.config))
    setup_logging(args.verbose, cfg.secrets)
    return cfg


def doctor(args: argparse.Namespace) -> int:
    try:
        cfg = load(args)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 1

    print(f"ao3bot {__version__} doctor")
    _row("config", str(cfg.path))
    for warning in _permission_warnings(cfg):
        _row("", f"warning: {warning}")

    a = cfg.ao3
    if a.logged_in:
        _row("ao3", f"logs in as {a.username} (password ********)")
    elif a.username:
        _row("ao3", f"logged out; public pages of {a.username} only")
    else:
        _row("ao3", "logged out (no username)")
    _row("sources", ", ".join(a.sources))
    if "manual" in a.sources:
        found = "found" if a.manual_ids_file.is_file() else "missing; create it with one work ID or URL per line"
        _row("manual ids", f"{a.manual_ids_file} ({found})")
    _row("poll", f"every {a.poll_minutes} min, backfill newest {a.backfill_newest}, adult works {'on' if a.adult_ok else 'off'}")

    d = cfg.device
    where = d.host if d.name == d.host else f"{d.name} at {d.host}"
    _row("reader", f"{where}, folder {d.folder}")
    _row("updates", f"{d.update_mode}, cleanup {d.cleanup_old} after {d.cleanup_grace_days} days")
    width, height = cfg.epub.max_image
    _row("epub", f"images up to {width}x{height}")

    _row("data dir", str(cfg.data_dir))
    try:
        with closing(open_db(cfg.state_db)) as conn:
            version = schema_version(conn)
            counts = row_counts(conn)
    except (OSError, sqlite3.Error, StateError) as e:
        _row("state.db", f"FAILED: {e}")
        return 1
    _row(
        "state.db",
        f"schema v{version}: {counts['works']} works, {counts['revisions']} revisions, "
        f"{counts['device_files']} files on readers",
    )
    _row("network", "not checked yet (later phases add AO3 and reader checks)")
    print("OK")
    return 0


def push(args: argparse.Namespace) -> int:
    try:
        cfg = load(args)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 1
    if args.interval < MIN_PUSH_INTERVAL:
        print(f"--interval must be at least {MIN_PUSH_INTERVAL} seconds", file=sys.stderr)
        return 1
    try:
        conn = open_db(cfg.state_db)
    except (OSError, sqlite3.Error, StateError) as e:
        print(f"state.db error: {e}", file=sys.stderr)
        return 1
    with closing(conn):
        if args.once:
            return _report_push(push_once(cfg, conn), cfg)
        print(f"checking for the reader at {cfg.device.host} every {args.interval} s; Ctrl+C to stop")
        try:
            while True:
                result = push_once(cfg, conn)
                if result.eventful:
                    _report_push(result, cfg)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0


def _report_push(result: PushResult, cfg: Config) -> int:
    if not result.reachable:
        print(f"reader at {cfg.device.host} isn't answering; is it on File Transfer > Join Network?")
        return 0
    print(f"reader {cfg.device.name}: {result.model or '?'}, CrossPoint {result.firmware or '?'}, folder {result.folder or '?'}")
    for name in result.uploaded:
        _row("uploaded", name)
    for name in result.adopted:
        _row("already on", name)
    for note in result.skipped:
        _row("skipped", note)
    for error in result.errors:
        _row("error", error)
    if result.interrupted:
        _row("stopped", "the reader went away partway through; the rest goes next time")
    print(
        f"done: {len(result.uploaded)} uploaded, {len(result.adopted)} already on the reader, "
        f"{len(result.skipped)} skipped, {len(result.errors)} errors"
    )
    return 1 if result.errors else 0


def _row(label: str, value: str) -> None:
    print(f"  {label:<11} {value}")


def _permission_warnings(cfg: Config) -> list[str]:
    """On the Pi, a config file holding a password should be readable by its owner only."""
    if os.name != "posix" or not cfg.ao3.password:
        return []
    mode = stat.S_IMODE(cfg.path.stat().st_mode)
    if mode & 0o077:
        return [f"config holds a password but is mode {mode:o}; run: chmod 600 {cfg.path}"]
    return []
