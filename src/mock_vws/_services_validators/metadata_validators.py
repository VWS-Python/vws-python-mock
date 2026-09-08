"""Validators for application metadata."""

import binascii
import logging
from http import HTTPStatus

from beartype import beartype

from mock_vws._base64_decoding import decode_base64
from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import (
    FailError,
    MetadataTooLargeError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_metadata_size(*, context: ValidatorContext) -> None:
    """Validate that the given application metadata is a string or 1024 *
    1024
    bytes or fewer.

    Args:
        context: The context of the request.

    Raises:
        MetadataTooLargeError: Application metadata is given and it is too
            large.
    """
    request_json = context.request_json
    application_metadata = request_json.get("application_metadata")
    if application_metadata is None:
        return
    decoded = decode_base64(encoded_data=application_metadata)

    max_metadata_bytes = 1024 * 1024 - 1
    if len(decoded) <= max_metadata_bytes:
        return

    _LOGGER.warning(msg="The application metadata is too large.")
    raise MetadataTooLargeError


@beartype
def validate_metadata_encoding(*, context: ValidatorContext) -> None:
    """Validate that the given application metadata can be base64 decoded.

    Args:
        context: The context of the request.

    Raises:
        FailError: Application metadata is given and it cannot be base64
            decoded.
    """
    request_json = context.request_json
    application_metadata = request_json.get("application_metadata")

    if application_metadata is None:
        return

    try:
        decode_base64(encoded_data=application_metadata)
    except binascii.Error as exc:
        _LOGGER.warning(msg="The application metadata is not base64 encoded.")
        raise FailError(status_code=HTTPStatus.UNPROCESSABLE_ENTITY) from exc


@beartype
def validate_metadata_type(*, context: ValidatorContext) -> None:
    """Validate that the given application metadata is a string or NULL.

    Args:
        context: The context of the request.

    Raises:
        FailError: Application metadata is given and it is not a string or
            NULL.
    """
    request_json = context.request_json
    if "application_metadata" not in request_json:
        return

    application_metadata = request_json["application_metadata"]

    if application_metadata is None or isinstance(application_metadata, str):
        return

    _LOGGER.warning(msg="The application metadata is not a string or NULL.")
    raise FailError(status_code=HTTPStatus.BAD_REQUEST)
