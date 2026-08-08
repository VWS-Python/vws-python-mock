"""Validators for the fields given."""

import io
import logging
from email.message import EmailMessage
from typing import TYPE_CHECKING

from beartype import beartype
from werkzeug.formparser import MultiPartParser

from mock_vws._query_validators.exceptions import UnknownParametersError

if TYPE_CHECKING:
    from collections.abc import Mapping

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_extra_fields(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> None:
    """Validate that the no unknown fields are given.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        UnknownParametersError: Extra fields are given.
    """
    email_message = EmailMessage()
    email_message["Content-Type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary(failobj="")
    parser = MultiPartParser()
    fields, files = parser.parse(
        stream=io.BytesIO(initial_bytes=request_body),
        boundary=boundary.encode(encoding="utf-8"),
        content_length=len(request_body),
    )
    parsed_keys = fields.keys() | files.keys()
    known_parameters = {"image", "max_num_results", "include_target_data"}

    if not parsed_keys - known_parameters:
        return

    _LOGGER.warning(msg="Unknown parameters are given.")
    raise UnknownParametersError
