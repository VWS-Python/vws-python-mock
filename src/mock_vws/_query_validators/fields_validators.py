"""
Validators for the fields given.
"""

import cgi
import io
from typing import Dict

from mock_vws._query_validators.exceptions import UnknownParameters


def validate_extra_fields(
    request_headers: Dict[str, str],
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

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = cgi.parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    known_parameters = {'image', 'max_num_results', 'include_target_data'}

    if not parsed.keys() - known_parameters:
        return

    raise UnknownParameters
