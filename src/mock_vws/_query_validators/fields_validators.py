"""Validators for the fields given."""

import logging

from beartype import beartype

from mock_vws._query_validators.exceptions import UnknownParametersError
from mock_vws._query_validators.multipart import MultipartForm

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_extra_fields(*, form: MultipartForm) -> None:
    """Validate that the no unknown fields are given.

    Args:
        form: The parsed body of the request.

    Raises:
        UnknownParametersError: Extra fields are given.
    """
    parsed_keys = form.fields.keys() | form.files.keys()
    known_parameters = {"image", "max_num_results", "include_target_data"}

    if not bool(parsed_keys - known_parameters):
        return

    _LOGGER.warning(msg="Unknown parameters are given.")
    raise UnknownParametersError
