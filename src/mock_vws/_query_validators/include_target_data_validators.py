"""Validators for the ``include_target_data`` field."""

import logging
from collections.abc import Mapping

from beartype import beartype

from mock_vws._query_validators.exceptions import InvalidIncludeTargetDataError
from mock_vws._query_validators.multipart import parse_multipart

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_include_target_data(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate the ``include_target_data`` field is either an accepted
    value
    or not given.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        InvalidIncludeTargetDataError: The ``include_target_data`` field is not
            an accepted value.
    """
    fields, _ = parse_multipart(
        request_headers=request_headers,
        request_body=request_body,
    )
    include_target_data = fields.get(key="include_target_data", default="top")
    allowed_included_target_data = {"top", "all", "none"}
    if include_target_data.lower() in allowed_included_target_data:
        return

    _LOGGER.warning(
        msg="The include_target_data field is not an accepted value.",
    )
    raise InvalidIncludeTargetDataError(given_value=include_target_data)
