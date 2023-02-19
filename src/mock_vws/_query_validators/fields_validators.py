"""
Validators for the fields given.
"""

import io
from email.message import EmailMessage

import mock_vws._cgi as cgi
from mock_vws._query_validators.exceptions import UnknownParameters


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
    boundary = email_message.get_boundary().encode()
    parsed = cgi.parse_multipart(fp=body_file, pdict={"boundary": boundary})

    known_parameters = {"image", "max_num_results", "include_target_data"}

    if not parsed.keys() - known_parameters:
        return

    raise UnknownParameters
