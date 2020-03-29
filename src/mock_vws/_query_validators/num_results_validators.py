"""
Validators for the ``max_num_results`` fields.
"""

import cgi
import io
from typing import Dict, List

import wrapt
from requests import codes

from mock_vws._mock_common import parse_multipart
from mock_vws.database import VuforiaDatabase


@wrapt.decorator
def validate_max_num_results(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the ``max_num_results`` field is either an integer within range or
    not given.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the ``max_num_results`` field is either not
        an integer, or an integer out of range.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )
    [max_num_results] = parsed.get('max_num_results', ['1'])
    assert isinstance(max_num_results, str)
    invalid_type_error = (
        f"Invalid value '{max_num_results}' in form data part "
        "'max_result'. "
        'Expecting integer value in range from 1 to 50 (inclusive).'
    )

    try:
        max_num_results_int = int(max_num_results)
    except ValueError:
        context.status_code = codes.BAD_REQUEST
        return invalid_type_error

    java_max_int = 2147483647
    if max_num_results_int > java_max_int:
        context.status_code = codes.BAD_REQUEST
        return invalid_type_error

    if max_num_results_int < 1 or max_num_results_int > 50:
        context.status_code = codes.BAD_REQUEST
        out_of_range_error = (
            f'Integer out of range ({max_num_results_int}) in form data part '
            "'max_result'. Accepted range is from 1 to 50 (inclusive)."
        )
        return out_of_range_error

    return
