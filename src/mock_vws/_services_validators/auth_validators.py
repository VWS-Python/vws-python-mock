"""
Authorization header validators to use in the mock.
"""

from http import HTTPStatus
from typing import Dict, Set

from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._services_validators.exceptions import (
    AuthenticationFailure,
    Fail,
)
from mock_vws.database import VuforiaDatabase


def validate_auth_header_exists(request_headers: Dict[str, str]) -> None:
    """
    Validate that there is an authorization header given to a VWS endpoint.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        AuthenticationFailure: There is no "Authorization" header.
    """
    if "Authorization" not in request_headers:
        raise AuthenticationFailure


def validate_access_key_exists(
    request_headers: Dict[str, str],
    databases: Set[VuforiaDatabase],
) -> None:
    """
    Validate the authorization header includes an access key for a database.

    Args:
        request_headers: The headers sent with the request.
        databases: All Vuforia databases.

    Raises:
        Fail: The access key does not match a given database.
    """
    header = request_headers["Authorization"]
    first_part, _ = header.split(":")
    _, access_key = first_part.split(" ")
    for database in databases:
        if access_key == database.server_access_key:
            return

    raise Fail(status_code=HTTPStatus.BAD_REQUEST)


def validate_auth_header_has_signature(
    request_headers: Dict[str, str],
) -> None:
    """
    Validate the authorization header includes a signature.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        Fail: The "Authorization" header does not include a signature.
    """
    header = request_headers["Authorization"]
    if header.count(":") == 1 and header.split(":")[1]:
        return

    raise Fail(status_code=HTTPStatus.BAD_REQUEST)


def validate_authorization(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: Set[VuforiaDatabase],
) -> None:
    """
    Validate the authorization header given to a VWS endpoint.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Raises:
        AuthenticationFailure: No database matches the given authorization
            header.
    """
    database = get_database_matching_server_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    if database is None:
        raise AuthenticationFailure
