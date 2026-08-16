"""Common utilities for creating mock routes."""

import email.utils
import json
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from beartype import beartype

from mock_vws._constants import ResultCodes
from mock_vws.target import ImageTarget

# A database ID as it appears in the path of a reco counts report request.
DATABASE_ID_PATTERN = "[A-Za-z0-9_-]+"
# The path of the endpoint which requests a reco counts report.
RECO_COUNTS_REPORT_PATH_PATTERN = (
    f"/imagetargets/databases/{DATABASE_ID_PATTERN}/reports/recoCounts"
)
# The path which stands in for a reco counts report presigned URL.
RECO_COUNTS_DOWNLOAD_PATH_PATTERN = "/reports/recoCounts/[A-Za-z0-9]+"


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


@beartype
@dataclass(frozen=True, kw_only=True)
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
def sorted_targets(*, targets: Iterable[ImageTarget]) -> list[ImageTarget]:
    """Put targets into a deterministic order.

    Targets are held in a ``set``, so iterating over them gives an order which
    varies between runs. Endpoints which return lists of targets use this so
    that repeated runs agree with each other.

    Args:
        targets: The targets to order.

    Returns:
        The given targets, ordered by upload date and then by target ID.
    """
    return sorted(
        targets,
        key=lambda target: (target.upload_date, target.target_id),
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
def json_dump(*, body: dict[str, Any]) -> str:
    """
    Returns:
        JSON dump of data in the same way that Vuforia dumps data.
    """
    return json.dumps(obj=body, separators=(",", ":"))
