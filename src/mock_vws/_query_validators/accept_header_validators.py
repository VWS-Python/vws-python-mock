"""
Validators for the ``Accept`` header.
"""


import logging

from mock_vws._query_validators.exceptions import InvalidAcceptHeader

_LOGGER = logging.getLogger(__name__)


def validate_accept_header(request_headers: dict[str, str]) -> None:
    """
    Validate the accept header.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        InvalidAcceptHeader: The Accept header is given and is not
            'application/json' or '*/*'.
    """
    accept = request_headers.get("Accept")
    if accept in {"application/json", "*/*", None}:
        return

    _LOGGER.warning(
        msg="The Accept header is not 'application/json' or '*/*'.",
    )
    raise InvalidAcceptHeader
