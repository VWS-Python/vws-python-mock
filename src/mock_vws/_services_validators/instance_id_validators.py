"""Validators for VuMark instance IDs."""

import json
import logging

from beartype import beartype

from mock_vws._services_validators.exceptions import InvalidInstanceIdError

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_instance_id(*, request_body: bytes) -> None:
    """Validate the instance_id data given to the VuMark instance
    generation endpoint.

    Args:
        request_body: The body of the request.

    Raises:
        InvalidInstanceIdError: There is instance_id data given to the
            endpoint which is a JSON array or object, or which is empty.
    """
    if not request_body:
        return

    request_text = request_body.decode()
    if "instance_id" not in json.loads(s=request_text):
        return

    instance_id = json.loads(s=request_text)["instance_id"]

    if isinstance(instance_id, dict | list):
        _LOGGER.warning(
            msg=(
                'The value of "instance_id" is a JSON array or object. '
                "This is not allowed."
            ),
        )
        raise InvalidInstanceIdError

    if not instance_id:
        _LOGGER.warning(msg='The value of "instance_id" is empty.')
        raise InvalidInstanceIdError
