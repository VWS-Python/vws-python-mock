"""
Validators for the ``include_target_data`` field.
"""

import cgi
import io
from typing import Dict, List

import wrapt
from requests import codes

from mock_vws._mock_common import parse_multipart
from mock_vws.database import VuforiaDatabase
from mock_vws._query_validators.exceptions import InvalidIncludeTargetData



def validate_include_target_data(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the ``include_target_data`` field is either an accepted value or
    not given.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the ``include_target_data`` field is not an
        accepted value.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    [include_target_data] = parsed.get('include_target_data', ['top'])
    lower_include_target_data = include_target_data.lower()
    allowed_included_target_data = {'top', 'all', 'none'}
    if lower_include_target_data in allowed_included_target_data:
        return

    assert isinstance(include_target_data, str)
    raise InvalidIncludeTargetData(given_value=include_target_data)
