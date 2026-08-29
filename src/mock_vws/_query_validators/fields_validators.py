"""Validators for the fields given."""

import logging
from collections.abc import Mapping

from beartype import beartype

from mock_vws._query_validators.exceptions import UnknownParametersError
from mock_vws._query_validators.multipart import parse_multipart

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
        NoContentDispositionError: A part of the body has no
            ``Content-Disposition`` header.
    """
    fields, files = parse_multipart(
        request_headers=request_headers,
        request_body=request_body,
    )
    parsed_keys = fields.keys() | files.keys()
    known_parameters = {"image", "max_num_results", "include_target_data"}

    if not parsed_keys - known_parameters:
        return

    _LOGGER.warning(msg="Unknown parameters are given.")
    raise UnknownParametersError
