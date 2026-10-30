"""Validators for the project state."""

import logging

from beartype import beartype

from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import (
    ProjectHasNoApiAccessError,
    ProjectSuspendedError,
)
from mock_vws.states import States

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_project_state(*, context: ValidatorContext) -> None:
    """Validate the state of the project.

    Args:
        context: The context of the request.

    Raises:
        ProjectHasNoApiAccessError: The project has no API access.
        ProjectSuspendedError: The project is suspended.
    """
    match context.database.state:
        case States.PROJECT_HAS_NO_API_ACCESS:
            raise ProjectHasNoApiAccessError
        case States.PROJECT_SUSPENDED:
            raise ProjectSuspendedError
        case States.PROJECT_INACTIVE:
            pass
        case _:
            return
