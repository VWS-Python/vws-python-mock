"""Content-Length header validators to use in the mock."""

import logging
from collections.abc import Mapping

from beartype import beartype

from mock_vws._services_validators.exceptions import (
    AuthenticationFailureError,
    ContentLengthHeaderNotIntError,
    ContentLengthHeaderTooLargeError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_content_length_header_is_int(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate the ``Content-Length`` header is an integer.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        ContentLengthHeaderNotIntError: The content length header is not an
            integer
    """
    body_length = len(request_body)
    request_headers_dict = dict(request_headers)
    given_content_length = request_headers_dict.get(
        "Content-Length",
        body_length,
    )

    try:
        int(given_content_length)
    except ValueError as exc:
        _LOGGER.warning(msg="The Content-Length header is not an integer.")
        raise ContentLengthHeaderNotIntError from exc


@beartype
def validate_content_length_header_not_too_large(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate the ``Content-Length`` header is not too large.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        ContentLengthHeaderTooLargeError: The given content length header says
            that the content length is greater than the body length.
    """
    body_length = len(request_body)
    request_headers_dict = dict(request_headers)
    given_content_length = request_headers_dict.get(
        "Content-Length",
        body_length,
    )
    given_content_length_value = int(given_content_length)
    # We skip coverage here as running a test to cover this is very slow.
    if given_content_length_value > body_length:  # pragma: no cover
        _LOGGER.warning(msg="The Content-Length header is too large.")
        raise ContentLengthHeaderTooLargeError


@beartype
def validate_content_length_header_not_too_small(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate the ``Content-Length`` header is not too small.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        AuthenticationFailureError: The given content length header says that
            the content length is smaller than the body length.
    """
    body_length = len(request_body)
    request_headers_dict = dict(request_headers)
    given_content_length = request_headers_dict.get(
        "Content-Length",
        body_length,
    )
    given_content_length_value = int(given_content_length)

    if given_content_length_value < body_length:
        _LOGGER.warning(msg="The Content-Length header is too small.")
        raise AuthenticationFailureError
