"""Fixtures for requests-mock backend tests."""

import socket
from collections.abc import Callable

import pytest
from beartype import beartype


@pytest.fixture(name="unused_local_url")
def fixture_unused_local_url() -> Callable[[], str]:
    """Return a factory that allocates an unused local URL on each
    call.
    """

    @beartype
    def allocate_url() -> str:
        """Return a URL for a local address with nothing listening on
        it.
        """
        with socket.socket() as sock:
            sock.bind(("", 0))
            address = sock.getsockname()
            assert isinstance(address, tuple)
            assert isinstance(address[1], int)
            port: int = address[1]
        return f"http://localhost:{port}"

    return allocate_url
