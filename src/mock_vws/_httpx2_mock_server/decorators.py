"""Route HTTPX2 requests through RESPX."""

from collections.abc import Callable
from typing import ClassVar, Protocol

import httpx
import httpx2
import respx
from beartype import beartype
from respx.mocks import HTTPCoreMocker

from mock_vws._mock_common import Route
from mock_vws._respx_mock_server.decorators import start_respx_router

type Httpx2Router = respx.MockRouter


class _APIHandler(Protocol):
    """An API handler with mock routes."""

    routes: set[Route]


class HTTPCore2Mocker(HTTPCoreMocker):
    """Teach RESPX which HTTPX2 transport methods to patch."""

    name = "vws-httpcore2"
    targets: ClassVar[list[str]] = [
        "httpcore2._sync.connection.HTTPConnection",
        "httpcore2._sync.connection_pool.ConnectionPool",
        "httpcore2._sync.http_proxy.HTTPProxy",
        "httpcore2._async.connection.AsyncHTTPConnection",
        "httpcore2._async.connection_pool.AsyncConnectionPool",
        "httpcore2._async.http_proxy.AsyncHTTPProxy",
    ]


@beartype
def _to_httpx2_request(*, request: httpx.Request) -> httpx2.Request:
    """Convert RESPX's HTTPX request to the public HTTPX2 type."""
    return httpx2.Request(
        method=request.method,
        url=str(object=request.url),
        headers=request.headers.multi_items(),
        content=request.content,
    )


@beartype
def _connect_error(request: httpx.Request) -> httpx2.ConnectError:
    """Return the native HTTPX2 error for a blocked request."""
    return httpx2.ConnectError(
        message="Connection refused by mock",
        request=_to_httpx2_request(request=request),
    )


@beartype
def _timeout_error(request: httpx.Request) -> httpx2.ReadTimeout:
    """Return the native HTTPX2 error for a simulated timeout."""
    return httpx2.ReadTimeout(
        message="Response delay exceeded read timeout",
        request=_to_httpx2_request(request=request),
    )


def start_httpx2_router(
    *,
    mock_vws_api: _APIHandler,
    mock_vwq_api: _APIHandler,
    base_vws_url: str,
    base_vwq_url: str,
    response_delay_seconds: float,
    sleep_fn: Callable[[float], None],
    real_http: bool,
) -> Httpx2Router:
    """Route HTTPX2 requests to the Vuforia fakes through RESPX."""
    return start_respx_router(
        mock_vws_api=mock_vws_api,
        mock_vwq_api=mock_vwq_api,
        base_vws_url=base_vws_url,
        base_vwq_url=base_vwq_url,
        response_delay_seconds=response_delay_seconds,
        sleep_fn=sleep_fn,
        real_http=real_http,
        using=HTTPCore2Mocker.name,
        make_connect_error=_connect_error,
        make_timeout_error=_timeout_error,
    )
