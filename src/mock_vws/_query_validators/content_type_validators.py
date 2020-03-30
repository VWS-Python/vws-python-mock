"""
Validators for the ``Content-Type`` header.
"""

import cgi
from typing import Dict, List

import wrapt
from requests import codes

from mock_vws.database import VuforiaDatabase
from mock_vws._query_validators.exceptions import UnsupportedMediaType, BoundaryNotInBody, NoBoundaryFound



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
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

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
