"""
Validators for the ``include_target_data`` field.
"""

import io
import logging
from email.message import EmailMessage

import multipart

from mock_vws._query_validators.exceptions import InvalidIncludeTargetData

_LOGGER = logging.getLogger(__name__)


def validate_include_target_data(
    request_headers: dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate the ``include_target_data`` field is either an accepted value or
    not given.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        InvalidIncludeTargetData: The ``include_target_data`` field is not an
            accepted value.
    """
    body_file = io.BytesIO(request_body)

    email_message = EmailMessage()
    email_message["content-type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary()
    assert isinstance(boundary, str)
    parsed = multipart.MultipartParser(stream=body_file, boundary=boundary)

    parsed_include_target_data = parsed.get("include_target_data")
    if parsed_include_target_data is None:
        include_target_data = "top"
    else:
        include_target_data = parsed_include_target_data.value

    allowed_included_target_data = {"top", "all", "none"}
    if include_target_data.lower() in allowed_included_target_data:
        return

    assert isinstance(include_target_data, str)
    _LOGGER.warning(
        msg="The include_target_data field is not an accepted value.",
    )
    raise InvalidIncludeTargetData(given_value=include_target_data)
