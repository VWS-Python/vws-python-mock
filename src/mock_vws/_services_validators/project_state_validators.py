"""Validators for the project state."""

import logging

from beartype import beartype

from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import (
    ProjectHasNoApiAccessError,
    ProjectInactiveError,
    ProjectSuspendedError,
    ValidatorError,
)
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.states import States

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_project_state(*, context: ValidatorContext) -> None:
    """Validate the state of the project.

    Args:
        context: The context of the request.

    Raises:
        ProjectInactiveError: The project is inactive and this endpoint does
            not work with inactive projects.
    """
    state_errors: dict[States, type[ValidatorError]] = {
        States.PROJECT_HAS_NO_API_ACCESS: ProjectHasNoApiAccessError,
        States.PROJECT_SUSPENDED: ProjectSuspendedError,
    }
    error = state_errors.get(context.database.state)
    if error is not None:
        raise error

    if context.database.state != States.PROJECT_INACTIVE:
        return

    if (
        isinstance(context.database, CloudDatabase)
        and context.allowed_for_inactive_cloud_project
    ):
        return

    if isinstance(context.database, VuMarkDatabase):
        return

    _LOGGER.warning(msg="The project is inactive.")
    raise ProjectInactiveError
