"""Validators for the VWS request quota.

This behavior cannot be verified against the real Vuforia Web Services
without deliberately exhausting a database's request quota. It implements the
publicly documented behavior so that users can exercise their application's
quota-error handling with the mock.
"""

from beartype import beartype

from mock_vws._database_matchers import AnyDatabase
from mock_vws.database import CloudDatabase

from .exceptions import RequestQuotaReachedError


@beartype
def validate_request_quota(*, database: AnyDatabase) -> None:
    """Raise an error if the matching cloud database has no request
    quota.
    """
    if isinstance(database, CloudDatabase) and database.request_quota == 0:
        raise RequestQuotaReachedError
