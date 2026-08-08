"""Validators for the ``Accept`` header."""

import logging
from typing import TYPE_CHECKING

from beartype import beartype

from mock_vws._query_validators.exceptions import InvalidAcceptHeaderError

if TYPE_CHECKING:
    from collections.abc import Mapping

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_accept_header(request_headers: Mapping[str, str]) -> None:
    """Validate the accept header.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        InvalidAcceptHeaderError: The Accept header is given and is not
            'application/json' or '*/*'.
    """
    accept = request_headers.get("Accept")
    if accept in {"application/json", "*/*", None}:
        return

    _LOGGER.warning(
        msg="The Accept header is not 'application/json' or '*/*'.",
    )
    raise InvalidAcceptHeaderError
