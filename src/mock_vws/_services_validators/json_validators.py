"""
Validators for given JSON.
"""

import json
from http import HTTPStatus
from json.decoder import JSONDecodeError

from requests_mock import POST, PUT

from mock_vws._services_validators.exceptions import (
    Fail,
    UnnecessaryRequestBody,
)


def validate_json(
    request_body: bytes,
    request_method: str,
) -> None:
    """
    Validate that there is either no JSON given or the JSON given is valid.

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

    if request_method not in (POST, PUT):
        raise UnnecessaryRequestBody

    try:
        json.loads(request_body.decode())
    except JSONDecodeError as exc:
        raise Fail(status_code=HTTPStatus.BAD_REQUEST) from exc
