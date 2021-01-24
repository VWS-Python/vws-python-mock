"""
Helpers for getting databases which match keys given in requests.
"""

from __future__ import annotations

from typing import Dict, Iterable

from vws_auth_tools import authorization_header

from mock_vws.database import VuforiaDatabase


def get_database_matching_client_keys(
    request_headers: Dict[str, str],
    request_body: bytes | None,
    request_method: str,
    request_path: str,
    databases: Iterable[VuforiaDatabase],
) -> VuforiaDatabase | None:
    """
    Return which, if any, of the given databases is being accessed by the given
    client request.

    Args:
        request_headers: The headers sent with the request.
        request_body: The request body.
        request_method: The HTTP method of the request.
        request_path: The path of the request.
        databases: The databases to check for matches.

    Returns:
        The database which is being accessed by the given client request.
    """
    content_type = request_headers.get('Content-Type', '').split(';')[0]
    auth_header = request_headers.get('Authorization')
    content = request_body or b''
    date = request_headers.get('Date', '')

    for database in databases:
        expected_authorization_header = authorization_header(
            access_key=database.client_access_key,
            secret_key=database.client_secret_key,
            method=request_method,
            content=content,
            content_type=content_type,
            date=date,
            request_path=request_path,
        )

        if auth_header == expected_authorization_header:
            return database
    return None


def get_database_matching_server_keys(
    request_headers: Dict[str, str],
    request_body: bytes | None,
    request_method: str,
    request_path: str,
    databases: Iterable[VuforiaDatabase],
) -> VuforiaDatabase | None:
    """
    Return which, if any, of the given databases is being accessed by the given
    server request.

    Args:
        request_headers: The headers sent with the request.
        request_body: The request body.
        request_method: The HTTP method of the request.
        request_path: The path of the request.
        databases: The databases to check for matches.

    Returns:
        The database being accessed by the given server request.
    """
    content_type = request_headers.get('Content-Type', '').split(';')[0]
    auth_header = request_headers.get('Authorization')
    content = request_body or b''
    date = request_headers.get('Date', '')

    for database in databases:
        expected_authorization_header = authorization_header(
            access_key=database.server_access_key,
            secret_key=database.server_secret_key,
            method=request_method,
            content=content,
            content_type=content_type,
            date=date,
            request_path=request_path,
        )

        if auth_header == expected_authorization_header:
            return database
    return None
