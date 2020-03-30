"""
Validators for the ``Accept`` header.
"""

from typing import Dict

from mock_vws._query_validators.exceptions import InvalidAcceptHeader


def validate_accept_header(request_headers: Dict[str, str], ) -> None:
    """
    Validate the accept header.

    Args:
        request_headers: The headers sent with the request.

    Returns:
        The result of calling the endpoint.
        A `NOT_ACCEPTABLE` response if the Accept header is given and is not
        'application/json' or '*/*'.
    """
    accept = request_headers.get('Accept')
    if accept in ('application/json', '*/*', None):
        return

    raise InvalidAcceptHeader
