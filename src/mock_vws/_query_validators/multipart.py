"""Parsing of the ``multipart/form-data`` bodies given to the query
API.
"""

import io
import logging
from collections.abc import Mapping
from email.message import EmailMessage

from beartype import beartype
from werkzeug.datastructures import FileStorage, MultiDict
from werkzeug.formparser import MultiPartParser

from mock_vws._query_validators.exceptions import NoContentDispositionError

_LOGGER = logging.getLogger(name=__name__)


@beartype
def _parse_with_boundary(
    *,
    request_body: bytes,
    boundary: bytes,
) -> tuple[MultiDict[str, str], MultiDict[str, FileStorage]]:
    """Parse a multipart body, requiring it to be complete.

    Args:
        request_body: The body of the request.
        boundary: The multipart boundary, without its leading dashes.

    Returns:
        The fields and the files parsed from the multipart body.

    Raises:
        ValueError: The body is not a complete multipart body.
    """
    parser = MultiPartParser()
    return parser.parse(
        stream=io.BytesIO(initial_bytes=request_body),
        boundary=boundary,
        content_length=len(request_body),
    )


@beartype
def parse_multipart(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
) -> tuple[MultiDict[str, str], MultiDict[str, FileStorage]]:
    """Parse the multipart body of a query request.

    Vuforia accepts a body which ends before its closing boundary, as a
    client which is cut off mid-upload sends, and treats the end of the body
    as the end of the part being uploaded.  ``MultiPartParser`` rejects such a
    body, so we give it the closing boundary which the client did not send.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Returns:
        The fields and the files parsed from the multipart body.

    Raises:
        NoContentDispositionError: The body ends within the headers of a part,
            or a part has no ``Content-Disposition`` header, so no part can be
            named.
    """
    email_message = EmailMessage()
    email_message["Content-Type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary(failobj="").encode(encoding="utf-8")
    closing_boundary = b"\r\n--" + boundary + b"--\r\n"

    # A body which ends part-way through the closing boundary keeps those
    # bytes: Vuforia gives them to the part being uploaded rather than
    # ignoring them.  We therefore try the body as it was sent before we try
    # it without its incomplete closing boundary.
    without_partial_boundary = request_body
    for length in reversed(range(1, len(closing_boundary))):
        if request_body.endswith(closing_boundary[:length]):
            without_partial_boundary = request_body[:-length]
            break

    candidates = (
        request_body,
        # The body ended within the data of a part.
        request_body + closing_boundary,
        # The body ended part-way through a header of a part, so the blank
        # line which ends the headers of that part is missing too.
        request_body + b"\r\n" + closing_boundary,
        # The body ended part-way through the closing boundary.
        without_partial_boundary + closing_boundary,
    )

    for candidate in candidates:
        try:
            return _parse_with_boundary(
                request_body=candidate,
                boundary=boundary,
            )
        except ValueError:
            continue

    # Every remaining body is one in which a part has no usable
    # ``Content-Disposition`` header, either because the body ends before that
    # header is complete or because the part does not have one.
    _LOGGER.warning(msg="A part has no Content-Disposition header.")
    raise NoContentDispositionError
