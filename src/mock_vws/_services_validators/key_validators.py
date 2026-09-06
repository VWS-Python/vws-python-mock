"""Validators for JSON keys."""

import json
import logging
from http import HTTPStatus

from beartype import beartype

from mock_vws._services_validators.context import ValidatorContext

from .exceptions import FailError

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_keys(*, context: ValidatorContext) -> None:
    """Validate the request keys given to a VWS endpoint.

    Args:
        context: The context of the request.

    Raises:
        FailError: Any given keys are not allowed, or if any required keys are
            missing.
    """
    allowed_keys = context.mandatory_keys | context.optional_keys
    request_json = json.loads(s=context.request_body.decode())
    given_keys = set(request_json.keys())
    all_given_keys_allowed = given_keys.issubset(allowed_keys)
    all_mandatory_keys_given = context.mandatory_keys.issubset(given_keys)

    if all_given_keys_allowed and all_mandatory_keys_given:
        return

    _LOGGER.warning(msg="Invalid keys given to endpoint.")
    raise FailError(status_code=HTTPStatus.BAD_REQUEST)
