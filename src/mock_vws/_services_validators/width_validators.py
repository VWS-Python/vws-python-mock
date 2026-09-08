"""Validators for the width field."""

import logging
from http import HTTPStatus

from beartype import beartype

from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import FailError

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_width(*, context: ValidatorContext) -> None:
    """Validate the width argument given to a VWS endpoint.

    Args:
        context: The context of the request.

    Raises:
        FailError: Width is given and is not a positive number.
    """
    request_json = context.request_json
    if "width" not in request_json:
        return

    width = request_json["width"]

    width_is_number = isinstance(width, int | float)
    width_positive = width_is_number and width > 0

    if not width_positive:
        _LOGGER.warning(msg="Width is not a positive number.")
        raise FailError(status_code=HTTPStatus.BAD_REQUEST)
