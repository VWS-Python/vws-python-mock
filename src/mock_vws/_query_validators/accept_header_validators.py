"""
Validators for the ``Accept`` header.
"""

from typing import Dict, List

from mock_vws._query_validators.exceptions import InvalidAcceptHeader
from mock_vws.database import VuforiaDatabase


def validate_accept_header(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the accept header.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Returns:
        The result of calling the endpoint.
        A `NOT_ACCEPTABLE` response if the Accept header is given and is not
        'application/json' or '*/*'.
    """
    accept = request_headers.get('Accept')
    if accept in ('application/json', '*/*', None):
        return

    raise InvalidAcceptHeader
