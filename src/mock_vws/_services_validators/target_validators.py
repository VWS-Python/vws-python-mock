"""Validators for given target IDs."""

import logging

from beartype import beartype

from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import UnknownTargetError

_LOGGER = logging.getLogger(name=__name__)
_TARGETS_WITH_INSTANCE_PATH_LENGTH = 4


@beartype
def target_id_from_path(*, request_path: str) -> str:
    """Return the target ID which a request path names.

    Args:
        request_path: The path of the request.

    Returns:
        The target ID in the path, which is the last segment except on the
        VuMark instance generation endpoint, where it is the segment before
        ``instances``.
    """
    split_path = request_path.split(sep="/")
    if (
        len(split_path) == _TARGETS_WITH_INSTANCE_PATH_LENGTH
        and split_path[-3] == "targets"
        and split_path[-1] == "instances"
    ):
        return split_path[-2]
    return split_path[-1]


@beartype
def validate_target_id_exists(*, context: ValidatorContext) -> None:
    """Validate that the target ID given in the request path exists in the
    database matching the request.

    Args:
        context: The context of the request.

    Raises:
        UnknownTargetError: There are no matching targets for the given target
            ID.
    """
    target_id = target_id_from_path(request_path=context.request_path)

    matching_targets = [
        target
        for target in context.database.not_deleted_targets
        if target.target_id == target_id
    ]
    if not bool(matching_targets):
        _LOGGER.warning('The target ID "%s" does not exist.', target_id)
        raise UnknownTargetError
