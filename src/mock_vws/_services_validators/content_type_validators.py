"""
Content-Type header validators to use in the mock.
"""


import logging

from requests_mock import POST, PUT

from mock_vws._services_validators.exceptions import AuthenticationFailure

_LOGGER = logging.getLogger(__name__)


def validate_content_type_header_given(
    request_headers: dict[str, str],
    request_method: str,
) -> None:
    """
    Validate that there is a non-empty content type header given if required.

    Args:
        request_headers: The headers sent with the request.
        request_method: The HTTP method of the request.

    Raises:
        AuthenticationFailure: No ``Content-Type`` header is given and the
            request requires one.
    """
    request_needs_content_type = bool(request_method in {POST, PUT})
    if request_headers.get("Content-Type") or not request_needs_content_type:
        return

    _LOGGER.warning(msg="No Content-Type header is given.")
    raise AuthenticationFailure
