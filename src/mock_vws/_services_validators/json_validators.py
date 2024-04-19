"""
Validators for given JSON.
"""

import json
import logging
from http import HTTPMethod, HTTPStatus
from json.decoder import JSONDecodeError

from mock_vws._services_validators.exceptions import (
    FailError,
    UnnecessaryRequestBodyError,
)

_LOGGER = logging.getLogger(__name__)


def validate_body_given(request_body: bytes, request_method: str) -> None:
    """
    Validate that no JSON is given for requests other than ``POST`` and ``PUT``
    requests.

    Args:
        request_body: The body of the request.
        request_method: The HTTP method of the request.

    Raises:
        UnnecessaryRequestBodyError: A request body was given for an endpoint
            which does not require one.
        FailError: The request body includes invalid JSON.
    """
    if not request_body:
        return

    if request_method not in {HTTPMethod.POST, HTTPMethod.PUT}:
        _LOGGER.warning(
            msg=(
                "A request body was given for an endpoint which does not "
                "require one."
            ),
        )
        raise UnnecessaryRequestBodyError


def validate_json(request_body: bytes) -> None:
    """
    Validate that any given body is valid JSON.

    Args:
        request_body: The body of the request.

    Raises:
        FailError: The request body includes invalid JSON.
    """
    if not request_body:
        return

    try:
        json.loads(request_body.decode())
    except JSONDecodeError as exc:
        _LOGGER.warning(msg="The request body is not valid JSON.")
        raise FailError(status_code=HTTPStatus.BAD_REQUEST) from exc
