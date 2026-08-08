"""Validators for the VWS target quota."""

from http import HTTPMethod
from typing import TYPE_CHECKING

from beartype import beartype

from mock_vws._database_matchers import (
    AnyDatabase,
    get_database_matching_server_keys,
)
from mock_vws.database import CloudDatabase

from .exceptions import TargetQuotaReachedError

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@beartype
def validate_target_quota(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
    request_method: str,
    request_path: str,
    databases: Iterable[AnyDatabase],
) -> None:
    """Raise an error when adding a target would exceed the quota."""
    if request_method != HTTPMethod.POST or request_path != "/targets":
        return

    database = get_database_matching_server_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )
    if (
        isinstance(database, CloudDatabase)
        and len(database.not_deleted_targets) >= database.target_quota
    ):
        raise TargetQuotaReachedError
