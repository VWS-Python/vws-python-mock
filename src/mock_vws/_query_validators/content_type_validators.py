"""
Validators for the ``Content-Type`` header.
"""

import cgi
from typing import Dict, List

from mock_vws._query_validators.exceptions import (
    BoundaryNotInBody,
    NoBoundaryFound,
    UnsupportedMediaType,
)
from mock_vws.database import VuforiaDatabase


def validate_content_type_header(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the ``Content-Type`` header.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Returns:
        The result of calling the endpoint.
        An ``UNSUPPORTED_MEDIA_TYPE`` response if the ``Content-Type`` header
        main part is not 'multipart/form-data'.
        A ``BAD_REQUEST`` response if the ``Content-Type`` header does not
        contain a boundary which is in the request body.
    """
    main_value, pdict = cgi.parse_header(request_headers['Content-Type'])
    if main_value != 'multipart/form-data':
        raise UnsupportedMediaType

    if 'boundary' not in pdict:
        raise NoBoundaryFound

    if pdict['boundary'].encode() not in request_body:
        raise BoundaryNotInBody
