"""Shared helpers for requests mock tests."""

import socket

from beartype import beartype


@beartype
def unused_local_url() -> str:
    """Return a URL for a local address with nothing listening on it."""
    with socket.socket() as sock:
        sock.bind(("", 0))
        address = sock.getsockname()
        assert isinstance(address, tuple)
        assert isinstance(address[1], int)
        port: int = address[1]
    return f"http://localhost:{port}"
