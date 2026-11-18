"""Load and check config.toml.

Every error is a single line, and none of them repeats a value from the file,
so a password can't leak through an error message.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_ENV = "AO3BOT_CONFIG"
DEFAULT_PATHS = (Path("config.toml"), Path("/etc/ao3bot/config.toml"))

SOURCES = ("manual", "marked_for_later", "bookmarks")
UPDATE_MODES = ("auto", "in_place", "side_by_side")
CLEANUP_MODES = ("after_switch", "manual")
MIN_POLL_MINUTES = 15


class ConfigError(Exception):
    """A problem with the config file, described in one line."""


_REQUIRED = object()

# section -> key -> (type, default). _REQUIRED means there's no default.
_SCHEMA: dict[str, dict[str, tuple[type, object]]] = {
    "ao3": {
        "username": (str, ""),
        "password": (str, ""),
        "sources": (list, ["manual"]),
        "manual_ids_file": (str, "ids.txt"),
        "poll_minutes": (int, 30),
        "adult_ok": (bool, True),
        "backfill_newest": (int, 10),
        "user_agent": (str, "ao3bot/0.1 (personal e-reader sync, one user)"),
    },
    "device": {
        "host": (str, _REQUIRED),
        "name": (str, ""),
        "folder": (str, "/AO3"),
        "update_mode": (str, "auto"),
        "cleanup_old": (str, "after_switch"),
        "cleanup_grace_days": (int, 7),
    },
    "epub": {
        "max_image": (str, "480x800"),
    },
    "paths": {
        "data_dir": (str, "data"),
    },
}

_TYPE_NAMES = {
    str: "a string",
    int: "a whole number",
    bool: "true or false",
    list: "a list of strings",
}


@dataclass(frozen=True)
class AO3Config:
    username: str
    password: str = field(repr=False)
    sources: tuple[str, ...]
    manual_ids_file: Path
    poll_minutes: int
    adult_ok: bool
    backfill_newest: int
    user_agent: str

    @property
    def logged_in(self) -> bool:
        """True when the bot will log in, i.e. both username and password are set."""
        return bool(self.username and self.password)


@dataclass(frozen=True)
class DeviceConfig:
    host: str
    name: str
    folder: str
    update_mode: str
    cleanup_old: str
    cleanup_grace_days: int


@dataclass(frozen=True)
class EpubConfig:
    max_image: tuple[int, int]


@dataclass(frozen=True)
class Config:
    path: Path
    ao3: AO3Config
    device: DeviceConfig
    epub: EpubConfig
    data_dir: Path

    @property
    def state_db(self) -> Path:
        return self.data_dir / "state.db"

    @property
    def library_dir(self) -> Path:
        return self.data_dir / "library"

    @property
    def secrets(self) -> list[str]:
        """Strings that must never appear in logs or output."""
        return [s for s in (self.ao3.password,) if s]


def find_config_path(explicit: str | None = None) -> Path:
    """Use --config if given, then $AO3BOT_CONFIG, then ./config.toml, then /etc/ao3bot/config.toml."""
    if explicit:
        return Path(explicit)
    from_env = os.environ.get(CONFIG_ENV)
    if from_env:
        return Path(from_env)
    for candidate in DEFAULT_PATHS:
        if candidate.is_file():
            return candidate
    raise ConfigError(
        "no config file found (looked for ./config.toml and /etc/ao3bot/config.toml); "
        "copy config.example.toml to config.toml, or pass --config"
    )


def load_config(path: Path | str) -> Config:
    path = Path(path).absolute()
    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"{path}: not found") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: not valid TOML: {e}") from None
    except OSError as e:
        raise ConfigError(f"{path}: can't read it ({e.strerror})") from None
    try:
        return _parse(raw, path)
    except ConfigError as e:
        raise ConfigError(f"{path}: {e}") from None


def _parse(raw: dict, path: Path) -> Config:
    for name in raw:
        if name not in _SCHEMA:
            raise ConfigError(f"unknown section [{name}]")
    values = {name: _read_section(raw, name) for name in _SCHEMA}
    ao3, dev, epub, paths = values["ao3"], values["device"], values["epub"], values["paths"]
    base = path.parent

    # [ao3]
    username = ao3["username"].strip()
    password = ao3["password"]
    sources = tuple(ao3["sources"])
    if not sources:
        raise ConfigError("[ao3] sources must list at least one source")
    for source in sources:
        if source not in SOURCES:
            raise ConfigError(f"[ao3] sources: unknown source '{source}' (known: {', '.join(SOURCES)})")
    if len(set(sources)) != len(sources):
        raise ConfigError("[ao3] sources lists the same source twice")
    if password and not username:
        raise ConfigError("[ao3] password is set but username is empty")
    if "marked_for_later" in sources and not (username and password):
        raise ConfigError("[ao3] the marked_for_later source needs username and password")
    if "bookmarks" in sources and not username:
        raise ConfigError("[ao3] the bookmarks source needs a username")
    if ao3["poll_minutes"] < MIN_POLL_MINUTES:
        raise ConfigError(f"[ao3] poll_minutes must be at least {MIN_POLL_MINUTES}, to go easy on AO3")
    if ao3["backfill_newest"] < 0:
        raise ConfigError("[ao3] backfill_newest can't be negative")
    if not ao3["user_agent"].strip():
        raise ConfigError("[ao3] user_agent can't be empty")

    # [device]
    host = dev["host"].strip()
    if not host:
        raise ConfigError("[device] host is empty")
    if "://" in host or "/" in host:
        raise ConfigError("[device] host should be an IP address or hostname, without http:// or a path")
    folder = dev["folder"]
    folder_ok = (
        folder.startswith("/")
        and len(folder) > 1
        and not folder.endswith("/")
        and not folder.startswith("/.")
        and "\\" not in folder
    )
    if not folder_ok:
        raise ConfigError('[device] folder must look like "/AO3": one leading slash, no trailing slash, not hidden')
    if dev["update_mode"] not in UPDATE_MODES:
        raise ConfigError(f"[device] update_mode must be one of: {', '.join(UPDATE_MODES)}")
    if dev["cleanup_old"] not in CLEANUP_MODES:
        raise ConfigError(f"[device] cleanup_old must be one of: {', '.join(CLEANUP_MODES)}")
    if dev["cleanup_grace_days"] < 0:
        raise ConfigError("[device] cleanup_grace_days can't be negative")

    # [epub]
    size = re.fullmatch(r"(\d{2,4})x(\d{2,4})", epub["max_image"])
    if not size:
        raise ConfigError('[epub] max_image must look like "480x800"')

    return Config(
        path=path,
        ao3=AO3Config(
            username=username,
            password=password,
            sources=sources,
            manual_ids_file=_resolve(base, ao3["manual_ids_file"]),
            poll_minutes=ao3["poll_minutes"],
            adult_ok=ao3["adult_ok"],
            backfill_newest=ao3["backfill_newest"],
            user_agent=ao3["user_agent"].strip(),
        ),
        device=DeviceConfig(
            host=host,
            name=dev["name"].strip() or host,
            folder=folder,
            update_mode=dev["update_mode"],
            cleanup_old=dev["cleanup_old"],
            cleanup_grace_days=dev["cleanup_grace_days"],
        ),
        epub=EpubConfig(max_image=(int(size.group(1)), int(size.group(2)))),
        data_dir=_resolve(base, paths["data_dir"]),
    )


def _read_section(raw: dict, section: str) -> dict:
    """Return the section's values, with defaults filled in and types checked."""
    schema = _SCHEMA[section]
    table = raw.get(section, {})
    if not isinstance(table, dict):
        raise ConfigError(f"[{section}] must be a section, not a single value")
    for key in table:
        if key not in schema:
            raise ConfigError(f"unknown key '{key}' in [{section}]")
    values = {}
    for key, (expected, default) in schema.items():
        if key not in table:
            if default is _REQUIRED:
                raise ConfigError(f"[{section}] {key} is required")
            values[key] = list(default) if isinstance(default, list) else default
            continue
        value = table[key]
        if not _has_type(value, expected):
            raise ConfigError(f"[{section}] {key} must be {_TYPE_NAMES[expected]}")
        values[key] = value
    return values


def _has_type(value: object, expected: type) -> bool:
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected is list:
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    return isinstance(value, expected)


def _resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path
