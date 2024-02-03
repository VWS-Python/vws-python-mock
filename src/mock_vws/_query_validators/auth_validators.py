"""
Authorization validators to use in the mock query API.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mock_vws._database_matchers import get_database_matching_client_keys
from mock_vws._query_validators.exceptions import (
    AuthenticationFailure,
    AuthHeaderMissing,
    MalformedAuthHeader,
)

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mock_vws.database import VuforiaDatabase


def validate_auth_header_exists(request_headers: dict[str, str]) -> None:
    """
    Validate that there is an authorization header given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        AuthHeaderMissing: There is no "Authorization" header.
    """
    if "Authorization" in request_headers:
        return

    _LOGGER.warning(msg="There is no authorization header.")
    raise AuthHeaderMissing


def validate_auth_header_number_of_parts(
    request_headers: dict[str, str],
) -> None:
    """
    Validate the authorization header includes text either side of a space.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        MalformedAuthHeader: The "Authorization" header is not as expected.
    """
    header = request_headers["Authorization"]
    parts = header.split(" ")
    expected_number_of_parts = 2
    if len(parts) == expected_number_of_parts and parts[1]:
        return

    _LOGGER.warning(msg="The authorization header is malformed.")
    raise MalformedAuthHeader


def validate_client_key_exists(
    request_headers: dict[str, str],
    databases: set[VuforiaDatabase],
) -> None:
    """
    Validate the authorization header includes a client key for a database.

    Args:
        request_headers: The headers sent with the request.
        databases: All Vuforia databases.

    Raises:
        AuthenticationFailure: The client key is unknown.
    """
    header = request_headers["Authorization"]
    first_part, _ = header.split(":")
    _, access_key = first_part.split(" ")
    for database in databases:
        if access_key == database.client_access_key:
            return

    _LOGGER.warning(msg="The client key is unknown.")
    raise AuthenticationFailure


def validate_auth_header_has_signature(
    request_headers: dict[str, str],
) -> None:
    """
    Validate the authorization header includes a signature.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        MalformedAuthHeader: The "Authorization" header has no signature.
    """
    header = request_headers["Authorization"]
    if header.count(":") == 1 and header.split(":")[1]:
        return

    _LOGGER.warning(msg="The authorization header has no signature.")
    raise MalformedAuthHeader


def validate_authorization(
    request_path: str,
    request_headers: dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: set[VuforiaDatabase],
) -> None:
    """
    Validate the authorization header given to the query endpoint.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Raises:
        AuthenticationFailure: The "Authorization" header is not as expected.
    """
    try:
        get_database_matching_client_keys(
            request_headers=request_headers,
            request_body=request_body,
            request_method=request_method,
            request_path=request_path,
            databases=databases,
        )
    except ValueError:
        _LOGGER.warning(
            msg="The authorization header does not match any databases.",
        )
        raise AuthenticationFailure from ValueError
