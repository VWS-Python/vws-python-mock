"""Tests for transports through the `httpx2` mock.

Closing a transport closes the ``httpx2`` client underneath it.
Which addresses an asynchronous ``httpx2`` client can reach.
"""

import socket

import httpx2
import pytest
from vws.transports import AsyncHTTPX2Transport, HTTPX2Transport

from mock_vws import MockVWS
from tests.mock_vws.httpx2_mock.helpers import run


def _unused_local_url() -> str:
    """A URL of a local port which nothing is listening on.

    Returns:
        The URL of a port which was free when this was called.
    """
    with socket.socket() as sock:
        sock.bind(("", 0))
        address = sock.getsockname()
        assert isinstance(address, tuple)
        assert isinstance(address[1], int)
        port: int = address[1]
    return f"http://localhost:{port}"


async def _async_get(*, url: str) -> httpx2.Response:
    """Make an asynchronous ``httpx2`` request.

    Args:
        url: The URL to request.

    Returns:
        The response to the request.
    """
    async with httpx2.AsyncClient() as client:
        return await client.get(url=url, timeout=30)


def test_close() -> None:
    """A closed ``HTTPX2Transport`` cannot make a request."""
    transport = HTTPX2Transport()
    transport.close()

    with MockVWS(), pytest.raises(expected_exception=RuntimeError):
        _ = transport(
            method="GET",
            url="https://vws.vuforia.com/summary",
            headers={},
            data=b"",
            request_timeout=30.0,
        )


def test_aclose() -> None:
    """A closed ``AsyncHTTPX2Transport`` cannot make a request."""

    async def close_then_request() -> None:
        """Close the transport and then try to use it."""
        transport = AsyncHTTPX2Transport()
        await transport.aclose()
        await transport(
            method="GET",
            url="https://vws.vuforia.com/summary",
            headers={},
            data=b"",
            request_timeout=30.0,
        )

    with MockVWS(), pytest.raises(expected_exception=RuntimeError):
        run(coroutine=close_then_request())


def test_unmocked_address_blocked() -> None:
    """Requests to non-Vuforia addresses are blocked."""
    url = _unused_local_url()

    with (
        MockVWS(),
        pytest.raises(expected_exception=httpx2.ConnectError),
    ):
        _ = run(coroutine=_async_get(url=url))


def test_real_http() -> None:
    """With ``real_http``, requests reach the transport underneath.

    Nothing is listening on the address, so the error comes from that
    transport rather than from the mock.
    """
    url = _unused_local_url()

    with (
        MockVWS(real_http=True),
        pytest.raises(expected_exception=httpx2.ConnectError),
    ):
        _ = run(coroutine=_async_get(url=url))
