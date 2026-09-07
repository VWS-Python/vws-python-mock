"""Validators for the ``include_target_data`` field."""

import logging

from beartype import beartype

from mock_vws._query_validators.exceptions import InvalidIncludeTargetDataError
from mock_vws._query_validators.multipart import MultipartForm

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_include_target_data(*, form: MultipartForm) -> None:
    """Validate the ``include_target_data`` field is either an accepted
    value
    or not given.

    Args:
        form: The parsed body of the request.

    Raises:
        InvalidIncludeTargetDataError: The ``include_target_data`` field is not
            an accepted value.
    """
    include_target_data = form.fields.get("include_target_data", "top")
    allowed_included_target_data = {"top", "all", "none"}
    if include_target_data.lower() in allowed_included_target_data:
        return

    _LOGGER.warning(
        msg="The include_target_data field is not an accepted value.",
    )
    raise InvalidIncludeTargetDataError(given_value=include_target_data)
