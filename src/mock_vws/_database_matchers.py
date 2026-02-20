"""Helpers for getting databases which match keys given in requests."""

from collections.abc import Iterable, Mapping

from beartype import beartype
from vws_auth_tools import authorization_header

from mock_vws.database import CloudDatabase
from mock_vws.target_manager import AnyDatabase


@beartype
def get_database_matching_client_keys(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes | None,
    request_method: str,
    request_path: str,
    databases: Iterable[AnyDatabase],
) -> CloudDatabase:
    """Return the first of the given databases which is being accessed by
    the
    given client request.

    Args:
        request_headers: The headers sent with the request.
        request_body: The request body.
        request_method: The HTTP method of the request.
        request_path: The path of the request.
        databases: The databases to check for matches.

    Returns:
        The database which is being accessed by the given client request.

    Raises:
        ValueError: No database matches the given request.
    """
    request_headers_dict = dict(request_headers)
    content_type = request_headers_dict.get("Content-Type", "").split(sep=";")[
        0
    ]
    auth_header = request_headers_dict.get("Authorization")
    date = request_headers_dict.get("Date", "")

    for database in databases:
        if not isinstance(database, CloudDatabase):
            continue
        expected_authorization_header = authorization_header(
            access_key=database.client_access_key,
            secret_key=database.client_secret_key,
            method=request_method,
            content=request_body,
            content_type=content_type,
            date=date,
            request_path=request_path,
        )

        if auth_header == expected_authorization_header:
            return database
    raise ValueError


@beartype
def get_database_matching_server_keys(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes | None,
    request_method: str,
    request_path: str,
    databases: Iterable[AnyDatabase],
) -> AnyDatabase:
    """Return the first of the given databases which is being accessed by
    the
    given server request.

    Args:
        request_headers: The headers sent with the request.
        request_body: The request body.
        request_method: The HTTP method of the request.
        request_path: The path of the request.
        databases: The databases to check for matches.

    Returns:
        The database being accessed by the given server request.

    Raises:
        ValueError: No database matches the given request.
    """
    request_headers_dict = dict(request_headers)
    content_type_header = request_headers_dict.get("Content-Type", "")
    content_type = content_type_header.split(sep=";")[0]
    auth_header = request_headers_dict.get("Authorization")
    date = request_headers_dict.get("Date", "")

    for database in databases:
        expected_authorization_header = authorization_header(
            access_key=database.server_access_key,
            secret_key=database.server_secret_key,
            method=request_method,
            content=request_body,
            content_type=content_type,
            date=date,
            request_path=request_path,
        )

        if auth_header == expected_authorization_header:
            return database
    raise ValueError
