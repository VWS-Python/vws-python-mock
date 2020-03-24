"""
Content-Type header validators to use in the mock.
"""

import uuid
from typing import Any, Callable, Dict, Tuple, List

import json
from requests import codes
from requests_mock import POST, PUT
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump
from mock_vws._services_validators.exceptions import AuthenticationFailure
from mock_vws.database import VuforiaDatabase



def validate_content_type_header_given(
    request_text: str,
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
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
