"""Validators for the active flag."""

import logging
from http import HTTPStatus

from beartype import beartype

from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import FailError

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_active_flag(*, context: ValidatorContext) -> None:
    """Validate the active flag data given to the endpoint.

    Args:
        context: The context of the request.

    Raises:
        FailError: There is active flag data given to the endpoint which is not
            either a Boolean or NULL.
    """
    request_json = context.request_json
    if "active_flag" not in request_json:
        return

    active_flag = request_json["active_flag"]

    if active_flag in {True, False, None}:
        return

    _LOGGER.warning(
        msg=(
            'The value of "active_flag" is not a Boolean or NULL. '
            "This is not allowed."
        ),
    )
    raise FailError(status_code=HTTPStatus.BAD_REQUEST)
