"""Validators for VuMark instance IDs."""

import logging

from beartype import beartype

from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import (
    BadRequestError,
    InvalidInstanceIdError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_instance_id_type(*, context: ValidatorContext) -> None:
    """Validate the type of the instance_id data given to the VuMark
    instance generation endpoint.

    Args:
        context: The context of the request.

    Raises:
        BadRequestError: There is instance_id data given to the endpoint
            which is not a string.
    """
    instance_id = context.request_json["instance_id"]

    if isinstance(instance_id, str):
        return

    _LOGGER.warning(
        msg='The value of "instance_id" is not a string. This is not allowed.',
    )
    raise BadRequestError


@beartype
def validate_instance_id_not_empty(*, context: ValidatorContext) -> None:
    """Validate that the instance_id data given to the VuMark instance
    generation endpoint is not empty.

    Args:
        context: The context of the request.

    Raises:
        InvalidInstanceIdError: There is instance_id data given to the
            endpoint which is an empty string.
    """
    instance_id = context.request_json["instance_id"]

    if instance_id:
        return

    _LOGGER.warning(msg='The value of "instance_id" is empty.')
    raise InvalidInstanceIdError
