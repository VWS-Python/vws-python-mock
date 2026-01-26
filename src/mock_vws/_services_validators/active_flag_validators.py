"""Validators for the active flag."""

import json
import logging
from http import HTTPStatus

from beartype import beartype

from mock_vws._services_validators.exceptions import FailError

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_active_flag(*, request_body: bytes) -> None:
    """Validate the active flag data given to the endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        FailError: There is active flag data given to the endpoint which is not
            either a Boolean or NULL.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "active_flag" not in json.loads(s=request_text):
        return

    active_flag = json.loads(s=request_text).get("active_flag")

    if active_flag in {True, False, None}:
        return

    _LOGGER.warning(
        msg=(
            'The value of "active_flag" is not a Boolean or NULL. '
            "This is not allowed."
        ),
    )
    raise FailError(status_code=HTTPStatus.BAD_REQUEST)
