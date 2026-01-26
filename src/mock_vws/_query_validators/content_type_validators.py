"""Validators for the ``Content-Type`` header."""

import logging
from collections.abc import Mapping
from email.message import EmailMessage

from beartype import beartype

from mock_vws._query_validators.exceptions import (
    ImageNotGivenError,
    NoBoundaryFoundError,
    NoContentTypeError,
    UnsupportedMediaTypeError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_content_type_header(
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate the ``Content-Type`` header.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        UnsupportedMediaTypeError: The ``Content-Type`` header main part is not
            'multipart/form-data'.
        NoBoundaryFoundError: The ``Content-Type`` header does not contain a
            boundary.
        ImageNotGivenError: The boundary is not in the request body.
        NoContentTypeError: The content type header is either empty or not
            given.
    """
    request_headers_dict = dict(request_headers)
    content_type_header = request_headers_dict.get("Content-Type", "")
    if not content_type_header:
        _LOGGER.warning(msg="The content type header is empty.")
        raise NoContentTypeError

    email_message = EmailMessage()
    email_message["Content-Type"] = request_headers["Content-Type"]
    if email_message.get_content_type() not in {"multipart/form-data", "*/*"}:
        _LOGGER.warning(
            msg=(
                "The content type header main part is not multipart/form-data."
            ),
        )
        raise UnsupportedMediaTypeError

    boundary = email_message.get_boundary()
    if boundary is None:
        _LOGGER.warning(
            msg="The content type header does not contain a boundary.",
        )
        raise NoBoundaryFoundError

    if boundary.encode() not in request_body:
        _LOGGER.warning(msg="The boundary is not in the request body.")
        raise ImageNotGivenError
