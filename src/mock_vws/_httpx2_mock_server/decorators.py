"""Helpers for mocking Vuforia with httpx2.

The ``httpx2`` request, response and exception classes are distinct from
the ``httpx`` ones, and ``respx`` speaks ``httpx``, so ``httpx2`` gets a
mock path of its own. Requests and responses on this path are native
``httpx2`` objects from end to end, and no ``httpx2.alias_httpx`` call is
needed to use it.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, override
from unittest import mock
from urllib.parse import urlparse

import httpx2
from beartype import beartype
from mock_response_delay.for_httpx2 import delayed_httpx2_handler

from mock_vws._mock_common import RequestData, Route

_ResponseType = tuple[int, Mapping[str, str], str | bytes]
_Handler = Callable[[RequestData], _ResponseType]
_Httpx2Handler = Callable[[httpx2.Request], httpx2.Response]


class _APIHandler(Protocol):
    """An API handler with mock routes."""

    routes: set[Route]


@beartype
@dataclass(frozen=True, kw_only=True)
class _MockRoute:
    """One route of a fake API, ready to match ``httpx2`` requests.

    Args:
        url_pattern: The pattern which the URL of a request must match.
        http_method: The HTTP method which the route handles.
        handler: What answers a request which the route matches.
    """

    url_pattern: re.Pattern[str]
    http_method: str
    handler: _Httpx2Handler


@beartype
def _to_request_data(
    *,
    request: httpx2.Request,
    base_path: str,
) -> RequestData:
    """Convert an ``httpx2`` request to a ``RequestData``.

    Args:
        request: The ``httpx2`` request to convert.
        base_path: The base path prefix to strip from the request path.

    Returns:
        A ``RequestData`` with method, path, headers, and body set.
    """
    path = request.url.raw_path.decode(encoding="ascii")
    if len(base_path) > 0 and path.startswith(base_path):
        path = path[len(base_path) :]
    return RequestData(
        method=request.method,
        path=path,
        headers={key.title(): value for key, value in request.headers.items()},
        body=request.content,
    )


@beartype
def _httpx2_handler(
    *,
    handler: _Handler,
    base_path: str,
) -> _Httpx2Handler:
    """Make a handler of ``RequestData`` answer ``httpx2`` requests.

    Args:
        handler: The handler which takes a ``RequestData`` and returns a
            response tuple.
        base_path: The base path prefix to strip from the request path.

    Returns:
        A handler which takes an ``httpx2`` request and returns an
        ``httpx2`` response.
    """

    def respond(request: httpx2.Request) -> httpx2.Response:
        """Give a request to the handler.

        Args:
            request: The request to respond to.

        Returns:
            An ``httpx2`` response built from the return value of the
            handler.
        """
        request_data = _to_request_data(request=request, base_path=base_path)
        status_code, headers, body = handler(request_data)
        body_bytes = body.encode() if isinstance(body, str) else body
        return httpx2.Response(
            status_code=status_code,
            headers=headers,
            content=body_bytes,
        )

    return respond


@beartype
def _refuse(*, request: httpx2.Request) -> httpx2.ConnectError:
    """The error to raise for a request which no fake route matches.

    Args:
        request: The request which no fake route matches.

    Returns:
        The error to raise for the given request.
    """
    return httpx2.ConnectError(
        message="Connection refused by mock",
        request=request,
    )


@beartype
@dataclass(frozen=True, kw_only=True)
class _Fakes:
    """Answer ``httpx2`` requests with the fakes of the Vuforia APIs.

    Args:
        routes: The routes of the fakes.
    """

    routes: Sequence[_MockRoute]

    def match(self, *, request: httpx2.Request) -> _MockRoute | None:
        """The route which handles a request, if there is one.

        Args:
            request: The request to find a route for.

        Returns:
            The first route which matches the given request, or ``None`` if
            no route matches it.
        """
        url = str(object=request.url)
        for route in self.routes:
            if route.http_method != request.method:
                continue
            if bool(route.url_pattern.search(string=url)):
                return route
        return None


@beartype
class _SyncVuforiaTransport(httpx2.BaseTransport):
    """Give synchronous ``httpx2`` requests to the fakes of the Vuforia
    APIs.
    """

    def __init__(
        self,
        *,
        fakes: _Fakes,
        wrapped: httpx2.BaseTransport | None,
    ) -> None:
        """
        Args:
            fakes: The fakes which answer requests that a route matches.
            wrapped: The transport to give requests which no fake route
                matches to, or ``None`` to refuse those requests.
        """
        self._fakes = fakes
        self._wrapped = wrapped

    @override
    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        """Handle a request from a synchronous ``httpx2`` client.

        Args:
            request: The request to handle.

        Returns:
            The response from a fake, or from the transport which the
            client would have used if the mock were not running.

        Raises:
            Exception: A connection error is raised for a request which no
                fake route matches, unless unmatched requests are passed
                through.
        """
        _ = request.read()
        route = self._fakes.match(request=request)
        if route is not None:
            return route.handler(request)
        if self._wrapped is None:
            raise _refuse(request=request)
        return self._wrapped.handle_request(request=request)


@beartype
class _AsyncVuforiaTransport(httpx2.AsyncBaseTransport):
    """Give asynchronous ``httpx2`` requests to the fakes of the Vuforia
    APIs.
    """

    def __init__(
        self,
        *,
        fakes: _Fakes,
        wrapped: httpx2.AsyncBaseTransport | None,
    ) -> None:
        """
        Args:
            fakes: The fakes which answer requests that a route matches.
            wrapped: The transport to give requests which no fake route
                matches to, or ``None`` to refuse those requests.
        """
        self._fakes = fakes
        self._wrapped = wrapped

    @override
    async def handle_async_request(
        self,
        request: httpx2.Request,
    ) -> httpx2.Response:
        """Handle a request from an asynchronous ``httpx2`` client.

        Args:
            request: The request to handle.

        Returns:
            The response from a fake, or from the transport which the
            client would have used if the mock were not running.

        Raises:
            Exception: A connection error is raised for a request which no
                fake route matches, unless unmatched requests are passed
                through.
        """
        await request.aread()
        route = self._fakes.match(request=request)
        if route is not None:
            return route.handler(request)
        if self._wrapped is None:
            raise _refuse(request=request)
        return await self._wrapped.handle_async_request(request=request)


@beartype
@dataclass(frozen=True, kw_only=True)
class Httpx2Router:
    """A started patch of ``httpx2`` which routes requests to fakes.

    Args:
        stop_fns: What to call, in order, to undo the patch.
    """

    stop_fns: Sequence[Callable[[], None]]

    def stop(self) -> None:
        """Stop routing ``httpx2`` requests to the fakes."""
        for stop_fn in self.stop_fns:
            stop_fn()


def _mock_routes(
    *,
    api_base_urls: Sequence[tuple[_APIHandler, str]],
    response_delay_seconds: float,
    sleep_fn: Callable[[float], None],
) -> list[_MockRoute]:
    """The routes of fake APIs, ready to match ``httpx2`` requests.

    Args:
        api_base_urls: Each fake API, with the base URL which it is served
            at.
        response_delay_seconds: The number of seconds to delay responses.
        sleep_fn: The function to use for sleeping during delays.

    Returns:
        A route for each HTTP method of each route of each given API.
    """
    mock_routes: list[_MockRoute] = []
    for api, base_url in api_base_urls:
        base_path = urlparse(url=base_url).path.rstrip("/")
        for route in api.routes:
            url_pattern = base_url.rstrip("/") + route.path_pattern + "$"
            compiled_url_pattern = re.compile(pattern=url_pattern)
            handler = route.handler
            httpx2_handler = delayed_httpx2_handler(
                handler=_httpx2_handler(handler=handler, base_path=base_path),
                delay_seconds=response_delay_seconds,
                sleep_fn=sleep_fn,
            )
            mock_routes.extend(
                _MockRoute(
                    url_pattern=compiled_url_pattern,
                    http_method=http_method,
                    handler=httpx2_handler,
                )
                for http_method in route.http_methods
            )
    return mock_routes


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
    """Route ``httpx2`` requests to fakes of the Vuforia APIs.

    Every ``httpx2`` client, whether it was made before the mock started or
    while it is running, is routed, because the patched method is the one
    which a client uses to choose a transport for each request.

    Args:
        mock_vws_api: The VWS API handler.
        mock_vwq_api: The VWQ API handler.
        base_vws_url: The base URL for the VWS API.
        base_vwq_url: The base URL for the VWQ API.
        response_delay_seconds: The number of seconds to delay responses.
        sleep_fn: The function to use for sleeping during delays.
        real_http: Whether to pass through unmatched requests.

    Returns:
        A started router.
    """
    fakes = _Fakes(
        routes=_mock_routes(
            api_base_urls=(
                (mock_vws_api, base_vws_url),
                (mock_vwq_api, base_vwq_url),
            ),
            response_delay_seconds=response_delay_seconds,
            sleep_fn=sleep_fn,
        ),
    )

    # HTTPX2 has no public hook for intercepting clients created before the
    # mock starts. A public client extension API was proposed but closed as
    # out of scope: https://github.com/pydantic/httpx2/issues/121
    # RESPX patches the equivalent private HTTPX method:
    # https://github.com/lundberg/respx/blob/57d8c29705fdbbaeb5cd216f1ea3bb0386d7ba16/respx/mocks.py#L150
    # pylint: disable=protected-access
    original_sync = httpx2.Client._transport_for_url  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    original_async = httpx2.AsyncClient._transport_for_url  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    # pylint: enable=protected-access

    def sync_transport_for_url(
        self: httpx2.Client,
        url: httpx2.URL,
    ) -> httpx2.BaseTransport:
        """The transport which a synchronous client uses for a URL.

        Args:
            self: The client which is choosing a transport.
            url: The URL which a transport is being chosen for.

        Returns:
            A transport which gives requests to the fakes.
        """
        wrapped = original_sync(self=self, url=url) if real_http else None
        return _SyncVuforiaTransport(fakes=fakes, wrapped=wrapped)

    def async_transport_for_url(
        self: httpx2.AsyncClient,
        url: httpx2.URL,
    ) -> httpx2.AsyncBaseTransport:
        """The transport which an asynchronous client uses for a URL.

        Args:
            self: The client which is choosing a transport.
            url: The URL which a transport is being chosen for.

        Returns:
            A transport which gives requests to the fakes.
        """
        wrapped = original_async(self=self, url=url) if real_http else None
        return _AsyncVuforiaTransport(fakes=fakes, wrapped=wrapped)

    sync_patch = mock.patch.object(
        target=httpx2.Client,
        attribute="_transport_for_url",
        new=sync_transport_for_url,
    )
    async_patch = mock.patch.object(
        target=httpx2.AsyncClient,
        attribute="_transport_for_url",
        new=async_transport_for_url,
    )
    _ = sync_patch.start()
    _ = async_patch.start()
    return Httpx2Router(stop_fns=(async_patch.stop, sync_patch.stop))
