"""Validators for the ``max_num_results`` fields."""

import logging

from beartype import beartype

from mock_vws._query_validators.exceptions import (
    InvalidMaxNumResultsError,
    MaxNumResultsOutOfRangeError,
)
from mock_vws._query_validators.multipart import MultipartForm

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_max_num_results(*, form: MultipartForm) -> None:
    """Validate the ``max_num_results`` field is either an integer within
    range
    or not given.

    Args:
        form: The parsed body of the request.

    Raises:
        InvalidMaxNumResultsError: The ``max_num_results`` given is not an
            integer less than or equal to the max integer in Java.
        MaxNumResultsOutOfRangeError: The ``max_num_results`` given is not in
            range.
    """
    max_num_results = form.fields.get("max_num_results", "1")

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
