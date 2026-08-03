"""Validators for the VWS request quota.

This behavior cannot be verified against the real Vuforia Web Services
without deliberately exhausting a database's request quota. It implements the
publicly documented behavior so that users can exercise their application's
quota-error handling with the mock.
"""

from collections.abc import Iterable, Mapping

from beartype import beartype

from mock_vws._database_matchers import (
    AnyDatabase,
    get_database_matching_server_keys,
)
from mock_vws.database import CloudDatabase

from .exceptions import RequestQuotaReachedError


@beartype
def validate_request_quota(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
    request_method: str,
    request_path: str,
    databases: Iterable[AnyDatabase],
) -> None:
    """Raise an error if the matching cloud database has no request
    quota.
    """
    database = get_database_matching_server_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )
    if isinstance(database, CloudDatabase) and database.request_quota == 0:
        raise RequestQuotaReachedError
