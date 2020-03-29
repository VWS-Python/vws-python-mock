"""
Validators for the ``include_target_data`` field.
"""

import cgi
import io
from typing import Any, Callable, Dict, List, Tuple
from mock_vws.database import VuforiaDatabase

import wrapt
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._mock_common import parse_multipart


@wrapt.decorator
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
    body_file = io.BytesIO(request.body)

    _, pdict = cgi.parse_header(request.headers['Content-Type'])
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
    unexpected_target_data_message = (
        f"Invalid value '{include_target_data}' in form data part "
        "'include_target_data'. "
        "Expecting one of the (unquoted) string values 'all', 'none' or 'top'."
    )
    context.status_code = codes.BAD_REQUEST
    return unexpected_target_data_message
