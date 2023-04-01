"""
Validators for given JSON.
"""

import json
import logging
from http import HTTPStatus
from json.decoder import JSONDecodeError

from requests_mock import POST, PUT

from mock_vws._services_validators.exceptions import (
    Fail,
    UnnecessaryRequestBody,
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
        UnnecessaryRequestBody: A request body was given for an endpoint which
            does not require one.
        Fail: The request body includes invalid JSON.
    """
    if not request_body:
        return

    if request_method not in {POST, PUT}:
        _LOGGER.warning(
            msg=(
                "A request body was given for an endpoint which does not "
                "require one."
            ),
        )
        raise UnnecessaryRequestBody


def validate_json(request_body: bytes) -> None:
    """
    Validate that any given body is valid JSON.

    Args:
        request_body: The body of the request.

    Raises:
        Fail: The request body includes invalid JSON.
    """
    if not request_body:
        return

    try:
        json.loads(request_body.decode())
    except JSONDecodeError as exc:
        _LOGGER.warning(msg="The request body is not valid JSON.")
        raise Fail(status_code=HTTPStatus.BAD_REQUEST) from exc
