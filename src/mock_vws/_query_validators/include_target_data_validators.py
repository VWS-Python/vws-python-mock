"""
Validators for the ``include_target_data`` field.
"""

import io
from email.message import EmailMessage

import mock_vws._cgi as cgi
from mock_vws._query_validators.exceptions import InvalidIncludeTargetData


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
    boundary = email_message.get_boundary().encode()
    parsed = cgi.parse_multipart(fp=body_file, pdict={"boundary": boundary})

    [include_target_data] = parsed.get("include_target_data", ["top"])
    lower_include_target_data = include_target_data.lower()
    allowed_included_target_data = {"top", "all", "none"}
    if lower_include_target_data in allowed_included_target_data:
        return

    assert isinstance(include_target_data, str)
    raise InvalidIncludeTargetData(given_value=include_target_data)
