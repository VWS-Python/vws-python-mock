"""Validators for the VWS request quota.

This behavior cannot be verified against the real Vuforia Web Services
without deliberately exhausting a database's request quota. It implements the
publicly documented behavior so that users can exercise their application's
quota-error handling with the mock.
"""

from beartype import beartype

from mock_vws.database import CloudDatabase

from .context import ValidatorContext
from .exceptions import RequestQuotaReachedError


@beartype
def validate_request_quota(*, context: ValidatorContext) -> None:
    """Raise an error if the matching cloud database has no request
    quota.

    Args:
        context: The context of the request.

    Raises:
        RequestQuotaReachedError: The database's request quota is exhausted.
    """
    if (
        isinstance(context.database, CloudDatabase)
        and context.database.request_quota == 0
    ):
        raise RequestQuotaReachedError
