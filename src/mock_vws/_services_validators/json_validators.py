"""Validators for given JSON."""

import json
import logging
from http import HTTPMethod, HTTPStatus
from json.decoder import JSONDecodeError

from beartype import beartype

from mock_vws._services_validators.exceptions import (
    BadRequestError,
    FailError,
    UnnecessaryRequestBodyError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_body_given(*, request_body: bytes, request_method: str) -> None:
    """Validate that no JSON is given for requests other than ``POST`` and
    ``PUT`` requests.

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


@beartype
def validate_json(*, request_body: bytes, request_path: str) -> None:
    """Validate that any given body is valid JSON.

    Args:
        request_body: The body of the request.
        request_path: The path of the request.

    Raises:
        BadRequestError: The request body includes invalid JSON for the
            VuMark instance generation endpoint.
        FailError: The request body includes invalid JSON for other
            endpoints.
    """
    if not request_body:
        return

    try:
        json.loads(s=request_body.decode())
    except JSONDecodeError as exc:
        _LOGGER.warning(msg="The request body is not valid JSON.")
        if request_path.endswith("/instances"):
            raise BadRequestError from exc
        raise FailError(status_code=HTTPStatus.BAD_REQUEST) from exc
