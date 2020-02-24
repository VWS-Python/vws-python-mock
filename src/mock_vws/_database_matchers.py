"""
Helpers for getting databases which match keys given in requests.
"""

import base64
import hashlib
import hmac
from typing import Dict, Iterable, Optional

from mock_vws.database import VuforiaDatabase


def _compute_hmac_base64(key: bytes, data: bytes) -> bytes:
    """
    Return the Base64 encoded HMAC-SHA1 hash of the given `data` using the
    provided `key`.
    """
    hashed = hmac.new(key=key, msg=None, digestmod=hashlib.sha1)
    hashed.update(msg=data)
    return base64.b64encode(s=hashed.digest())


def _authorization_header(  # pylint: disable=too-many-arguments
    access_key: str,
    secret_key: str,
    method: str,
    content: bytes,
    content_type: str,
    date: str,
    request_path: str,
) -> str:
    """
    Return an `Authorization` header which can be used for a request made to
    the VWS API with the given attributes.

    Args:
        access_key: A VWS server or client access key.
        secret_key: A VWS server or client secret key.
        method: The HTTP method which will be used in the request.
        content: The request body which will be used in the request.
        content_type: The `Content-Type` header which will be used in the
            request.
        date: The current date which must exactly match the date sent in the
            `Date` header.
        request_path: The path to the endpoint which will be used in the
            request.

    Returns:
        An `Authorization` header which can be used for a request made to the
            VWS API with the given attributes.
    """
    hashed = hashlib.md5()
    hashed.update(content)
    content_md5_hex = hashed.hexdigest()

    components_to_sign = [
        method,
        content_md5_hex,
        content_type,
        date,
        request_path,
    ]
    string_to_sign = '\n'.join(components_to_sign)
    signature = _compute_hmac_base64(
        key=secret_key.encode(),
        data=bytes(
            string_to_sign,
            encoding='utf-8',
        ),
    )
    auth_header = f'VWS {access_key}:{signature.decode()}'
    return auth_header


def get_database_matching_client_keys(
    request_headers: Dict[str, str],
    request_body: Optional[bytes],
    request_method: str,
    request_path: str,
    databases: Iterable[VuforiaDatabase],
) -> Optional[VuforiaDatabase]:
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
        expected_authorization_header = _authorization_header(
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
    request_body: Optional[bytes],
    request_method: str,
    request_path: str,
    databases: Iterable[VuforiaDatabase],
) -> Optional[VuforiaDatabase]:
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
        expected_authorization_header = _authorization_header(
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
