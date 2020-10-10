"""
Validators for the ``Content-Type`` header.
"""

import cgi
from typing import Dict

from mock_vws._query_validators.exceptions import (
    ImageNotGiven,
    NoBoundaryFound,
    NoContentType,
    UnsupportedMediaType,
)


def validate_content_type_header(
    request_headers: Dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate the ``Content-Type`` header.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        UnsupportedMediaType: The ``Content-Type`` header main part is not
            'multipart/form-data'.
        NoBoundaryFound: The ``Content-Type`` header does not contain a
            boundary.
        ImageNotGiven: The boundary is not in the request body.
        NoContentType: The content type header is either empty or not given.
    """
    content_type_header = request_headers.get('Content-Type', '')
    main_value, pdict = cgi.parse_header(content_type_header)
    if content_type_header == '':
        raise NoContentType

    if main_value not in ('multipart/form-data', '*/*'):
        raise UnsupportedMediaType

    if 'boundary' not in pdict:
        raise NoBoundaryFound

    if pdict['boundary'].encode() not in request_body:
        raise ImageNotGiven
