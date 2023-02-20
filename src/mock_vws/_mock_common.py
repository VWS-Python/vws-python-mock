"""
Common utilities for creating mock routes.
"""

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Route:
    """
    A representation of a VWS route.

    Args:
        route_name: The name of the method.
        path_pattern: The end part of a URL pattern. E.g. `/targets` or
            `/targets/.+`.
        http_methods: HTTP methods that map to the route function.
    """

    route_name: str
    path_pattern: str
    http_methods: frozenset[str]


def json_dump(body: dict[str, Any]) -> str:
    """
    Returns:
        JSON dump of data in the same way that Vuforia dumps data.
    """
    return json.dumps(obj=body, separators=(",", ":"))
