"""Content-Length header validators to use in the mock."""

import logging

from beartype import beartype

from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import (
    AuthenticationFailureError,
    ContentLengthHeaderNotIntError,
    ContentLengthHeaderTooLargeError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def _given_content_length(*, context: ValidatorContext) -> str | int:
    """Return the given ``Content-Length``, or the real body length.

    Args:
        context: The context of the request.

    Returns:
        The value of the ``Content-Length`` header, or the length of the
        request body if no such header was given.
    """
    return dict(context.request_headers).get(
        "Content-Length",
        len(context.request_body),
    )


@beartype
def validate_content_length_header_is_int(
    *,
    context: ValidatorContext,
) -> None:
    """Validate the ``Content-Length`` header is an integer.

    Args:
        context: The context of the request.

    Raises:
        ContentLengthHeaderNotIntError: The content length header is not an
            integer
    """
    try:
        _ = int(_given_content_length(context=context))
    except ValueError as exc:
        _LOGGER.warning(msg="The Content-Length header is not an integer.")
        raise ContentLengthHeaderNotIntError from exc


@beartype
def validate_content_length_header_not_too_large(
    *,
    context: ValidatorContext,
) -> None:
    """Validate the ``Content-Length`` header is not too large.

    Args:
        context: The context of the request.

    Raises:
        ContentLengthHeaderTooLargeError: The given content length header says
            that the content length is greater than the body length.
    """
    given_content_length_value = int(_given_content_length(context=context))
    body_length = len(context.request_body)
    # We skip coverage here as running a test to cover this is very slow.
    if given_content_length_value > body_length:  # pragma: no cover
        _LOGGER.warning(msg="The Content-Length header is too large.")
        raise ContentLengthHeaderTooLargeError


@beartype
def validate_content_length_header_not_too_small(
    *,
    context: ValidatorContext,
) -> None:
    """Validate the ``Content-Length`` header is not too small.

    Args:
        context: The context of the request.

    Raises:
        AuthenticationFailureError: The given content length header says that
            the content length is smaller than the body length.
    """
    given_content_length_value = int(_given_content_length(context=context))

    if given_content_length_value < len(context.request_body):
        _LOGGER.warning(msg="The Content-Length header is too small.")
        raise AuthenticationFailureError
