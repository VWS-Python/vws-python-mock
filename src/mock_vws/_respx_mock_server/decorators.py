"""Helpers for mocking Vuforia with httpx via respx."""

import re
from collections.abc import Callable, Mapping
from urllib.parse import urlparse

import httpx
import respx

from mock_vws._mock_common import RequestData
from mock_vws._requests_mock_server.mock_web_query_api import (
    MockVuforiaWebQueryAPI,
)
from mock_vws._requests_mock_server.mock_web_services_api import (
    MockVuforiaWebServicesAPI,
)

_ResponseType = tuple[int, Mapping[str, str], str | bytes]


def _to_request_data(
    request: httpx.Request,
    *,
    base_path: str,
) -> RequestData:
    """Convert an httpx.Request to a RequestData.

    Args:
        request: The httpx request to convert.
        base_path: The base path prefix to strip from the request path.

    Returns:
        A RequestData with method, path, headers, and body set.
    """
    path = request.url.raw_path.decode(encoding="ascii")
    if base_path and path.startswith(base_path):
        path = path[len(base_path) :]
    return RequestData(
        method=request.method,
        path=path,
        headers={k.title(): v for k, v in request.headers.items()},
        body=request.content,
    )


def _block_unmatched(request: httpx.Request) -> httpx.Response:
    """Raise ConnectError for unmatched requests when real_http=False.

    Args:
        request: The unmatched httpx request.

    Raises:
        Exception: A connection error is always raised to block
            unmatched requests.
    """
    raise httpx.ConnectError(
        message="Connection refused by mock",
        request=request,
    )


def _make_respx_callback(
    *,
    handler: Callable[[RequestData], _ResponseType],
    base_path: str,
    delay_seconds: float,
    sleep_fn: Callable[[float], None],
) -> Callable[[httpx.Request], httpx.Response]:
    """Create a respx-compatible callback from a handler.

    Args:
        handler: A handler that takes a RequestData and returns a
            response tuple.
        base_path: The base path prefix to strip from the request path.
        delay_seconds: The number of seconds to delay the response by.
        sleep_fn: The function to use for sleeping during delays.

    Returns:
        A callback that takes an httpx.Request and returns an
        httpx.Response.
    """

    def callback(request: httpx.Request) -> httpx.Response:
        """Handle an httpx request by converting it and calling the
        handler.

        Args:
            request: The httpx request to handle.

        Returns:
            An httpx.Response built from the handler's return value.

        Raises:
            Exception: A timeout error is raised when the response
                delay exceeds the read timeout.
        """
        request_data = _to_request_data(
            request=request,
            base_path=base_path,
        )
        timeout_info: dict[str, float | None] = request.extensions.get(
            "timeout", {}
        )
        read_timeout = timeout_info.get("read")
        if read_timeout is not None and delay_seconds > read_timeout:
            sleep_fn(read_timeout)
            raise httpx.ReadTimeout(
                message="Response delay exceeded read timeout",
                request=request,
            )
        status_code, headers, body = handler(request_data)
        sleep_fn(delay_seconds)
        if isinstance(body, str):
            body = body.encode()
        return httpx.Response(
            status_code=status_code,
            headers=headers,
            content=body,
        )

    return callback


def start_respx_router(
    *,
    mock_vws_api: MockVuforiaWebServicesAPI,
    mock_vwq_api: MockVuforiaWebQueryAPI,
    base_vws_url: str,
    base_vwq_url: str,
    response_delay_seconds: float,
    sleep_fn: Callable[[float], None],
    real_http: bool,
) -> respx.MockRouter:
    """Configure and start a respx.MockRouter with Vuforia routes.

    Args:
        mock_vws_api: The VWS API handler.
        mock_vwq_api: The VWQ API handler.
        base_vws_url: The base URL for the VWS API.
        base_vwq_url: The base URL for the VWQ API.
        response_delay_seconds: The number of seconds to delay responses.
        sleep_fn: The function to use for sleeping during delays.
        real_http: Whether to pass through unmatched requests.

    Returns:
        A started respx.MockRouter.
    """
    router = respx.MockRouter(
        assert_all_called=False,
        assert_all_mocked=False,
    )

    for api, base_url in (
        (mock_vws_api, base_vws_url),
        (mock_vwq_api, base_vwq_url),
    ):
        base_path = urlparse(url=base_url).path.rstrip("/")
        for route in api.routes:
            url_pattern = base_url.rstrip("/") + route.path_pattern + "$"
            compiled_url_pattern = re.compile(pattern=url_pattern)

            for http_method in route.http_methods:
                original_callback = getattr(api, route.route_name)
                router.route(
                    method=http_method,
                    url=compiled_url_pattern,
                ).mock(
                    side_effect=_make_respx_callback(
                        handler=original_callback,
                        base_path=base_path,
                        delay_seconds=response_delay_seconds,
                        sleep_fn=sleep_fn,
                    ),
                )

    if real_http:
        router.route().pass_through()
    else:
        router.route().mock(side_effect=_block_unmatched)

    router.start()
    return router
