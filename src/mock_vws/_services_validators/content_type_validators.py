"""
Content-Type header validators to use in the mock.
"""

from typing import Dict

from requests_mock import POST, PUT

from mock_vws._services_validators.exceptions import AuthenticationFailure


def validate_content_type_header_given(
    request_headers: Dict[str, str],
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
    request_needs_content_type = bool(request_method in (POST, PUT))
    if request_headers.get('Content-Type') or not request_needs_content_type:
        return

    raise AuthenticationFailure
