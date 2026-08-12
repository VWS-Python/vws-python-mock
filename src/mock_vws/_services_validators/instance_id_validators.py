"""Validators for VuMark instance IDs."""

import json
import logging

from beartype import beartype

from mock_vws._services_validators.exceptions import (
    BadRequestError,
    InvalidInstanceIdError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_instance_id_type(*, request_body: bytes) -> None:
    """Validate the type of the instance_id data given to the VuMark
    instance generation endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        BadRequestError: There is instance_id data given to the endpoint
            which is not a string.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "instance_id" not in json.loads(s=request_text):
        return

    instance_id = json.loads(s=request_text)["instance_id"]

    if isinstance(instance_id, str):
        return

    _LOGGER.warning(
        msg='The value of "instance_id" is not a string. This is not allowed.',
    )
    raise BadRequestError


@beartype
def validate_instance_id_not_empty(*, request_body: bytes) -> None:
    """Validate that the instance_id data given to the VuMark instance
    generation endpoint is not empty.

    Args:
        request_body: The body of the request.

    Raises:
        InvalidInstanceIdError: There is instance_id data given to the
            endpoint which is an empty string.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "instance_id" not in json.loads(s=request_text):
        return

    instance_id = json.loads(s=request_text)["instance_id"]

    if instance_id:
        return

    _LOGGER.warning(msg='The value of "instance_id" is empty.')
    raise InvalidInstanceIdError
