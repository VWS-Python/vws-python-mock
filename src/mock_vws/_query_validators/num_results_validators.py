"""
Validators for the ``max_num_results`` fields.
"""

import cgi
import io
from typing import Dict, List

from mock_vws._mock_common import parse_multipart
from mock_vws._query_validators.exceptions import (
    InvalidMaxNumResults,
    MaxNumResultsOutOfRange,
)
from mock_vws.database import VuforiaDatabase


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
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Raises:
        InvalidMaxNumResults: The ``max_num_results`` given is not an integer
            less than or equal to the max integer in Java.
        MaxNumResultsOutOfRange: The ``max_num_results`` given is not in range.
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
        raise InvalidMaxNumResults(given_value=max_num_results)

    if max_num_results_int < 1 or max_num_results_int > 50:
        raise MaxNumResultsOutOfRange(given_value=max_num_results)
