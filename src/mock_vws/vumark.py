"""Public configuration types for the VuMark Generation API."""

from enum import StrEnum, unique
from http import HTTPStatus

from beartype import beartype


@beartype
@unique
class VuMarkGenerationFailure(StrEnum):
    """A configured failure returned by the VuMark Generation API mock."""

    QUOTA_EXCEEDED = "QuotaExceeded"
    LICENSE_CHECK_FAILED = "LicenseCheckFailed"
    AUTHORIZATION_FAILED = "AuthorizationFailed"

    @property
    def status_code(self) -> HTTPStatus:
        """Return the HTTP status documented for this failure."""
        if self is VuMarkGenerationFailure.AUTHORIZATION_FAILED:
            return HTTPStatus.UNAUTHORIZED
        return HTTPStatus.FORBIDDEN
