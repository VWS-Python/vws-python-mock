"""Content-Type header validators to use in the mock."""

import logging
from collections.abc import Mapping
from http import HTTPMethod

from beartype import beartype

from mock_vws._services_validators.exceptions import AuthenticationFailureError

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_content_type_header_given(
    *,
    request_headers: Mapping[str, str],
    request_method: str,
) -> None:
    """Validate that there is a non-empty content type header given if
    required.

    Args:
        request_headers: The headers sent with the request.
        request_method: The HTTP method of the request.

    Raises:
        AuthenticationFailureError: No ``Content-Type`` header is given and the
            request requires one.
    """
    request_headers_dict = dict(request_headers)
    request_needs_content_type = bool(
        request_method in {HTTPMethod.POST, HTTPMethod.PUT},
    )
    if (
        request_headers_dict.get("Content-Type")
        or not request_needs_content_type
    ):
        return

    _LOGGER.warning(msg="No Content-Type header is given.")
    raise AuthenticationFailureError
