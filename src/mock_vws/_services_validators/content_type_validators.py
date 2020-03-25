"""
Content-Type header validators to use in the mock.
"""

from typing import Dict, List

from requests_mock import POST, PUT

from mock_vws._services_validators.exceptions import AuthenticationFailure
from mock_vws.database import VuforiaDatabase


def validate_content_type_header_given(
    request_headers: Dict[str, str],
    request_method: str,
) -> None:
    """
    Validate that there is a non-empty content type header given if required.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNAUTHORIZED` response if there is no "Content-Type" header or the
        given header is empty.
    """
    request_needs_content_type = bool(request_method in (POST, PUT))
    if request_headers.get('Content-Type') or not request_needs_content_type:
        return

    raise AuthenticationFailure
