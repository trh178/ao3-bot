import socket

import pytest


def test_outside_connections_are_blocked():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match="must not make network requests"):
            sock.connect(("203.0.113.1", 443))  # TEST-NET-3: never routable anyway
    finally:
        sock.close()


def test_localhost_is_allowed():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(server.getsockname())
    finally:
        client.close()
        server.close()
