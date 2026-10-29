"""Common utilities for creating mock routes."""

import email.utils
import json
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Final, override

from beartype import beartype
from pydantic import JsonValue

from mock_vws._constants import ResultCodes


@beartype
class MissingSchemeError(Exception):
    """Raised when a URL is missing a schema."""

    def __init__(self, url: str) -> None:
        """
        Args:
            url: The URL which is missing a scheme.
        """
        super().__init__()
        self.url = url

    @override
    def __str__(self) -> str:
        """
        Give a string representation of this error with a
        suggestion.
        """
        return (
            f'Invalid URL "{self.url}": No scheme supplied. '
            f'Perhaps you meant "https://{self.url}".'
        )


@beartype
@dataclass(frozen=True, kw_only=True)
class RequestData:
    """A library-agnostic representation of an HTTP request.

    Args:
        method: The HTTP method of the request.
        path: The path of the request.
        headers: The headers sent with the request.
        body: The body of the request.
    """

    method: str
    path: str
    headers: Mapping[str, str]
    body: bytes


type RouteHandler = Callable[
    [RequestData],
    tuple[int, Mapping[str, str], str | bytes],
]


@beartype
@dataclass(frozen=True, kw_only=True)
class Route:
    """A representation of a VWS route.

    Args:
        handler: The callback which handles the route.
        path_pattern: The end part of a URL pattern. E.g. `/targets` or
            `/targets/.+`.
        http_methods: HTTP methods that map to the route function.
    """

    handler: RouteHandler
    path_pattern: str
    http_methods: Iterable[str]


@beartype
@dataclass(frozen=True, kw_only=True)
class RouteDefinition[API]:
    """An API route whose handler has not yet been bound to an
    instance.
    """

    handler: Callable[
        [API, RequestData],
        tuple[int, Mapping[str, str], str | bytes],
    ]
    path_pattern: str
    http_methods: Iterable[str]

    def bind(self, *, api: API) -> Route:
        """Bind the route handler to an API instance."""
        return Route(
            handler=partial(self.handler, api),
            path_pattern=self.path_pattern,
            http_methods=self.http_methods,
        )


@beartype
def result_code_response_text(*, result_code: ResultCodes) -> str:
    """
    Args:
        result_code: The result code to give in the response body.

    Returns:
        The body of a Vuforia error response, with a new transaction ID.
    """
    body = {
        "transaction_id": uuid.uuid4().hex,
        "result_code": result_code.value,
    }
    return json_dump(body=body)


@beartype
def http_date() -> str:
    """
    Returns:
        The current time, formatted for an HTTP ``Date`` header.
    """
    return email.utils.formatdate(timeval=None, localtime=False, usegmt=True)


@beartype
def json_dump(*, body: Mapping[str, JsonValue]) -> str:
    """
    Returns:
        JSON dump of data in the same way that Vuforia dumps data.
    """
    return json.dumps(obj=body, separators=(",", ":"))


# NGINX, which sits in front of both Vuforia APIs, reads each header line
# into an 8 KiB buffer which also holds the line's terminating CRLF.
# A line of 8190 bytes is accepted and a line of 8191 bytes is rejected.
MAX_HEADER_LINE_LENGTH: Final[int] = 8190


@beartype
def has_oversized_header_line(*, request_headers: Mapping[str, str]) -> bool:
    """Whether any header line is too long for NGINX's header buffer.

    A header line is the header name, a colon, a space and the value, as
    sent on the wire.

    Args:
        request_headers: The headers sent with the request.

    Returns:
        Whether any header line is longer than ``MAX_HEADER_LINE_LENGTH``.
    """
    return any(
        len(f"{name}: {value}".encode()) > MAX_HEADER_LINE_LENGTH
        for name, value in request_headers.items()
    )
