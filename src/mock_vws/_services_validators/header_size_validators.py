"""Validators for the size of request headers."""

import logging
from collections.abc import Mapping

from beartype import beartype

from mock_vws._mock_common import has_oversized_header_line
from mock_vws._services_validators.exceptions import (
    RequestHeaderOrCookieTooLargeError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_header_lines_not_too_large(
    *,
    request_headers: Mapping[str, str],
) -> None:
    """Validate that no header line is too long for NGINX.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        RequestHeaderOrCookieTooLargeError: A header line is longer than
            NGINX's header buffer.
    """
    if has_oversized_header_line(request_headers=request_headers):
        _LOGGER.warning(msg="A request header line is too large.")
        raise RequestHeaderOrCookieTooLargeError
