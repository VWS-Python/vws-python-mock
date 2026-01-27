"""Authorization header validators to use in the mock."""

import logging
from http import HTTPStatus
from typing import TYPE_CHECKING

from beartype import beartype

from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._services_validators.exceptions import (
    AuthenticationFailureError,
    FailError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from mock_vws.database import VuforiaDatabase

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_auth_header_exists(*, request_headers: Mapping[str, str]) -> None:
    """Validate that there is an authorization header given to a VWS
    endpoint.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        AuthenticationFailureError: There is no "Authorization" header.
    """
    if "Authorization" not in request_headers:
        _LOGGER.warning(msg="There is no authorization header.")
        raise AuthenticationFailureError


@beartype
def validate_access_key_exists(
    *,
    request_headers: Mapping[str, str],
    databases: Iterable[VuforiaDatabase],
) -> None:
    """Validate the authorization header includes an access key for a
    database.

    Args:
        request_headers: The headers sent with the request.
        databases: All Vuforia databases.

    Raises:
        FailError: The access key does not match a given database.
    """
    header = request_headers["Authorization"]
    first_part, _ = header.split(sep=":")
    _, access_key = first_part.split(sep=" ")
    for database in databases:
        if access_key == database.server_access_key:
            return

    _LOGGER.warning(
        'The access key "%s" does not match a known database.',
        access_key,
    )
    raise FailError(status_code=HTTPStatus.BAD_REQUEST)


@beartype
def validate_auth_header_has_signature(
    *,
    request_headers: Mapping[str, str],
) -> None:
    """Validate the authorization header includes a signature.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        FailError: The "Authorization" header does not include a signature.
    """
    header = request_headers["Authorization"]
    if header.count(":") == 1 and header.split(sep=":")[1]:
        return

    _LOGGER.warning(
        msg="The authorization header does not include a signature.",
    )
    raise FailError(status_code=HTTPStatus.BAD_REQUEST)


@beartype
def validate_authorization(
    *,
    request_path: str,
    request_headers: Mapping[str, str],
    request_body: bytes,
    request_method: str,
    databases: Iterable[VuforiaDatabase],
) -> None:
    """Validate the authorization header given to a VWS endpoint.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Raises:
        AuthenticationFailureError: No database matches the given authorization
            header.
    """
    try:
        get_database_matching_server_keys(
            request_headers=request_headers,
            request_body=request_body,
            request_method=request_method,
            request_path=request_path,
            databases=databases,
        )
    except ValueError as exc:
        _LOGGER.warning(
            msg="No database matches the given authorization header.",
        )
        raise AuthenticationFailureError from exc
