"""
Validators for the width field.
"""

import json
import numbers
from http import HTTPStatus

from mock_vws._services_validators.exceptions import Fail


def validate_width(request_body: bytes) -> None:
    """
    Validate the width argument given to a VWS endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        Fail: Width is given and is not a positive number.
    """

    if not request_body:
        return

    request_text = request_body.decode()
    if 'width' not in json.loads(request_text):
        return

    width = json.loads(request_text).get('width')

    width_is_number = isinstance(width, numbers.Number)
    width_positive = width_is_number and width > 0

    if not width_positive:
        raise Fail(status_code=HTTPStatus.BAD_REQUEST)
