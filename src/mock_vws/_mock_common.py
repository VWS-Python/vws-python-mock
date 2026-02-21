"""Common utilities for creating mock routes."""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from beartype import beartype


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class Route:
    """A representation of a VWS route.

    Args:
        route_name: The name of the method.
        path_pattern: The end part of a URL pattern. E.g. `/targets` or
            `/targets/.+`.
        http_methods: HTTP methods that map to the route function.
    """

    route_name: str
    path_pattern: str
    http_methods: Iterable[str]


@beartype
def json_dump(*, body: dict[str, Any]) -> str:
    """
    Returns:
        JSON dump of data in the same way that Vuforia dumps data.
    """
    return json.dumps(obj=body, separators=(",", ":"))
