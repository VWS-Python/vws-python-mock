"""Validators for the VWS target quota."""

from http import HTTPMethod

from beartype import beartype

from mock_vws._database_matchers import AnyDatabase
from mock_vws.database import CloudDatabase

from .exceptions import TargetQuotaReachedError


@beartype
def validate_target_quota(
    *,
    request_method: str,
    request_path: str,
    database: AnyDatabase,
) -> None:
    """Raise an error when adding a target would exceed the quota."""
    if request_method != HTTPMethod.POST or request_path != "/targets":
        return

    if (
        isinstance(database, CloudDatabase)
        and len(database.not_deleted_targets) >= database.target_quota
    ):
        raise TargetQuotaReachedError
