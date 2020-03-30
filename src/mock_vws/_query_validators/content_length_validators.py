"""
Content-Length header validators to use in the mock.
"""

from typing import Dict, List

from mock_vws._query_validators.exceptions import (
    AuthenticationFailureGoodFormatting,
    ContentLengthHeaderNotInt,
    ContentLengthHeaderTooLarge,
)
from mock_vws.database import VuforiaDatabase


def validate_content_length_header_is_int(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the ``Content-Length`` header is an integer.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Raises:
        The result of calling the endpoint.
        A ``BAD_REQUEST`` response if the content length header is not an
        integer.
    """
    given_content_length = request_headers['Content-Length']

    try:
        int(given_content_length)
    except ValueError:
        raise ContentLengthHeaderNotInt


def validate_content_length_header_not_too_large(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the ``Content-Length`` header is not too large.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Raises:
        The result of calling the endpoint.
        A ``GATEWAY_TIMEOUT`` response if the given content length header says
        that the content length is greater than the body length.
    """
    given_content_length = request_headers['Content-Length']

    body_length = len(request_body if request_body else b'')
    given_content_length_value = int(given_content_length)
    if given_content_length_value > body_length:
        raise ContentLengthHeaderTooLarge


def validate_content_length_header_not_too_small(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the ``Content-Length`` header is not too small.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Raises:
        The result of calling the endpoint.
        An ``UNAUTHORIZED`` response if the given content length header says
        that the content length is smaller than the body length.
    """
    given_content_length = request_headers['Content-Length']

    body_length = len(request_body if request_body else b'')
    given_content_length_value = int(given_content_length)

    if given_content_length_value < body_length:
        raise AuthenticationFailureGoodFormatting
