"""Validators for VuMark generation requests."""

from collections.abc import Mapping

from beartype import beartype

from mock_vws._services_validators.exceptions import (
    InvalidAcceptHeaderError,
    InvalidInstanceIdError,
)

VALID_ACCEPT_HEADERS = frozenset(
    {"image/svg+xml", "image/png", "application/pdf"}
)


@beartype
def validate_accept_header(request_headers: Mapping[str, str]) -> str:
    """Validate the Accept header for VuMark generation.

    Args:
        request_headers: The headers sent with the request.

    Returns:
        The validated Accept header value.

    Raises:
        InvalidAcceptHeaderError: The Accept header is missing or invalid.
    """
    accept_header: str = request_headers.get("Accept") or ""
    if accept_header not in VALID_ACCEPT_HEADERS:
        raise InvalidAcceptHeaderError
    return accept_header


@beartype
def validate_instance_id(instance_id: object) -> str:
    """Validate the instance_id for VuMark generation.

    In the real Vuforia API, validation depends on the VuMark type:
    - Numeric: 0-9 only
    - Bytes: hex characters 0-9a-f
    - String: printable ASCII characters

    For this mock, we accept any non-empty string.

    Args:
        instance_id: The instance ID from the request body.

    Returns:
        The validated instance ID.

    Raises:
        InvalidInstanceIdError: The instance_id is missing or invalid.
    """
    if not instance_id or not isinstance(instance_id, str):
        raise InvalidInstanceIdError
    return instance_id
