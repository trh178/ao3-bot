import ipaddress
import socket
from pathlib import Path

import pytest

from ao3bot.config import load_config
from ao3bot.state import open_db

from .fake_reader import FakeReader

REPO = Path(__file__).resolve().parent.parent

MINIMAL = '[device]\nhost = "192.168.1.50"\n'


def _is_loopback(address) -> bool:
    host = address[0] if isinstance(address, tuple) else address
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests must never reach AO3 or anything else off this machine.

    Connections to localhost are still allowed, for the fake reader.
    """
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guard(address):
        if not _is_loopback(address):
            raise RuntimeError(f"tests must not make network requests (tried {address!r})")

    def connect(self, address):
        guard(address)
        return real_connect(self, address)

    def connect_ex(self, address):
        guard(address)
        return real_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)


@pytest.fixture
def write_config(tmp_path):
    """Write a config.toml into a temp folder and return its path."""

    def _write(body: str) -> Path:
        path = tmp_path / "config.toml"
        path.write_text(body, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def reader(tmp_path):
    """A fake CrossPoint reader on localhost, with its SD card in a temp folder."""
    with FakeReader(tmp_path / "sd") as r:
        yield r


@pytest.fixture
def make_env(tmp_path, reader):
    """make_env(device_extra="") -> (config pointing at the fake reader, open state.db)."""
    conns = []

    def _make(device_extra: str = ""):
        path = tmp_path / "config.toml"
        path.write_text(f'[device]\nhost = "{reader.host}"\nname = "test-x4"\n{device_extra}\n', encoding="utf-8")
        cfg = load_config(path)
        conn = open_db(cfg.state_db)
        conns.append(conn)
        return cfg, conn

    yield _make
    for conn in conns:
        conn.close()


@pytest.fixture
def env(make_env):
    return make_env()
