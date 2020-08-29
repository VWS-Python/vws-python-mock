"""
Content-Length header validators to use in the mock.
"""

from typing import Dict

from mock_vws._query_validators.exceptions import (
    AuthenticationFailureGoodFormatting,
    ContentLengthHeaderNotInt,
    ContentLengthHeaderTooLarge,
)


def validate_content_length_header_is_int(
    request_headers: Dict[str, str],
) -> None:
    """
    Validate the ``Content-Length`` header is an integer.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        ContentLengthHeaderNotInt: ``Content-Length`` header is not an integer.
    """
    given_content_length = request_headers['Content-Length']

    try:
        int(given_content_length)
    except ValueError as exc:
        raise ContentLengthHeaderNotInt from exc


def validate_content_length_header_not_too_large(
    request_headers: Dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate the ``Content-Length`` header is not too large.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        ContentLengthHeaderTooLarge: The given content length header says that
            the content length is greater than the body length.
    """
    given_content_length = request_headers['Content-Length']

    body_length = len(request_body if request_body else b'')
    given_content_length_value = int(given_content_length)
    if given_content_length_value > body_length:
        raise ContentLengthHeaderTooLarge


def validate_content_length_header_not_too_small(
    request_headers: Dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate the ``Content-Length`` header is not too small.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        AuthenticationFailureGoodFormatting: The given content length header
            says that the content length is smaller than the body length.
    """
    given_content_length = request_headers['Content-Length']

    body_length = len(request_body if request_body else b'')
    given_content_length_value = int(given_content_length)

    if given_content_length_value < body_length:
        raise AuthenticationFailureGoodFormatting
