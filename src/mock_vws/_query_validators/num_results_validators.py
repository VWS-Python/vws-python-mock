"""
Validators for the ``max_num_results`` fields.
"""

import io
import logging
from collections.abc import Mapping
from email.message import EmailMessage

from beartype import beartype
from werkzeug.formparser import MultiPartParser

from mock_vws._query_validators.exceptions import (
    InvalidMaxNumResultsError,
    MaxNumResultsOutOfRangeError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_max_num_results(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate the ``max_num_results`` field is either an integer within range
    or not given.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        InvalidMaxNumResultsError: The ``max_num_results`` given is not an
            integer less than or equal to the max integer in Java.
        MaxNumResultsOutOfRangeError: The ``max_num_results`` given is not in
            range.
    """
    email_message = EmailMessage()
    email_message["Content-Type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary(failobj="")
    parser = MultiPartParser()
    fields, _ = parser.parse(
        stream=io.BytesIO(initial_bytes=request_body),
        boundary=boundary.encode(encoding="utf-8"),
        content_length=len(request_body),
    )
    max_num_results = fields.get(key="max_num_results", default="1")

    try:
        max_num_results_int = int(max_num_results)
    except ValueError as exc:
        _LOGGER.warning(msg="The max_num_results field is not an integer.")
        raise InvalidMaxNumResultsError(given_value=max_num_results) from exc

    java_max_int = 2147483647
    if max_num_results_int > java_max_int:
        _LOGGER.warning(msg="The max_num_results field is too large.")
        raise InvalidMaxNumResultsError(given_value=max_num_results)

    max_allowed_results = 50
    if max_num_results_int < 1 or max_num_results_int > max_allowed_results:
        _LOGGER.warning(msg="The max_num_results field is out of range.")
        raise MaxNumResultsOutOfRangeError(given_value=max_num_results)
