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
from mock_vws._query_validators.exceptions import InvalidMaxNumResults, MaxNumResultsOutOfRange



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

    try:
        max_num_results_int = int(max_num_results)
    except ValueError:
        raise InvalidMaxNumResults(given_value=max_num_results)

    java_max_int = 2147483647
    if max_num_results_int > java_max_int:
        raise InvalidMaxNumResults

    if max_num_results_int < 1 or max_num_results_int > 50:
        raise MaxNumResultsOutOfRange(given_value=max_num_results)
