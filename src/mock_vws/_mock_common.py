"""Common utilities for creating mock routes."""

import datetime
import email.utils
import json
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final, override

from beartype import beartype

from mock_vws._constants import ResultCodes
from mock_vws.target import ImageTarget

# A database ID as it appears in the path of a reco counts report request.
DATABASE_ID_PATTERN = "[A-Za-z0-9_-]+"
# The path of the endpoint which requests a reco counts report.
RECO_COUNTS_REPORT_PATH_PATTERN = (
    f"/imagetargets/databases/{DATABASE_ID_PATTERN}/reports/recoCounts"
)
# The path which stands in for a reco counts report presigned URL, with the
# query string of that URL.
# Any file name is matched, so that a file which no request generated gives
# the response which cloud storage gives for a missing object rather than
# leaving the request unmatched.
RECO_COUNTS_DOWNLOAD_PATH_PATTERN = (
    f"/reports/{DATABASE_ID_PATTERN}/[^/?]+(\\?.*)?"
)


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
def _upload_order_key(target: ImageTarget) -> tuple[datetime.datetime, str]:
    """Give the sort key which orders targets by upload date, then ID.

    Args:
        target: The target to give a sort key for.

    Returns:
        The target's upload date and ID.
    """
    return (target.upload_date, target.target_id)


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
    return sorted(targets, key=_upload_order_key)


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
