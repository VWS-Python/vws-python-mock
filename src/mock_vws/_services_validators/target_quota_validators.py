"""Validators for the VWS target quota."""

from beartype import beartype

from mock_vws.database import CloudDatabase

from .context import ValidatorContext
from .exceptions import TargetQuotaReachedError


@beartype
def validate_target_quota(*, context: ValidatorContext) -> None:
    """Raise an error when adding a target would exceed the quota.

    Args:
        context: The context of the request.

    Raises:
        TargetQuotaReachedError: The database already holds as many targets
            as its quota allows.
    """
    if (
        isinstance(context.database, CloudDatabase)
        and len(context.database.not_deleted_targets)
        >= context.database.target_quota
    ):
        raise TargetQuotaReachedError
