"""
Validators for the fields given.
"""

import io
import logging
from email.message import EmailMessage

import multipart

from mock_vws._query_validators.exceptions import UnknownParameters

_LOGGER = logging.getLogger(__name__)


def validate_extra_fields(
    request_headers: dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate that the no unknown fields are given.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        UnknownParameters: Extra fields are given.
    """
    body_file = io.BytesIO(request_body)

    email_message = EmailMessage()
    email_message["content-type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary()
    assert isinstance(boundary, str)
    parsed = multipart.MultipartParser(stream=body_file, boundary=boundary)
    parsed_keys = {part.name for part in parsed.parts()}
    known_parameters = {"image", "max_num_results", "include_target_data"}

    if not parsed_keys - known_parameters:
        return

    _LOGGER.warning(msg="Unknown parameters are given.")
    raise UnknownParameters
