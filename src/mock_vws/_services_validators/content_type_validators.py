"""Content-Type header validators to use in the mock."""

import logging

from beartype import beartype

from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import AuthenticationFailureError

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_content_type_header_given(*, context: ValidatorContext) -> None:
    """Validate that there is a non-empty content type header given.

    Args:
        context: The context of the request.

    Raises:
        AuthenticationFailureError: No ``Content-Type`` header is given.
    """
    if bool(dict(context.request_headers).get("Content-Type")):
        return

    _LOGGER.warning(msg="No Content-Type header is given.")
    raise AuthenticationFailureError
