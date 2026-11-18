import ipaddress
import socket
from pathlib import Path

import pytest

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

    Connections to localhost are still allowed, for the fake reader in phase 5.
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
