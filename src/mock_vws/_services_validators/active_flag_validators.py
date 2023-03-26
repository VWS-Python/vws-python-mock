"""
Validators for the active flag.
"""

import json
import logging
from http import HTTPStatus

from mock_vws._services_validators.exceptions import Fail

_LOGGER = logging.getLogger(__name__)


def validate_active_flag(request_body: bytes) -> None:
    """
    Validate the active flag data given to the endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        Fail: There is active flag data given to the endpoint which is not
            either a Boolean or NULL.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "active_flag" not in json.loads(request_text):
        return

    active_flag = json.loads(request_text).get("active_flag")

    if active_flag is None or isinstance(active_flag, bool):
        return

    _LOGGER.warning(
        msg=(
            'The value of "active_flag" is not a Boolean or NULL.'
            "This is not allowed."
        ),
    )
    raise Fail(status_code=HTTPStatus.BAD_REQUEST)
