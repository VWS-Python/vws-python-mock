"""Validators for the project state."""

import logging
from http import HTTPMethod

from beartype import beartype

from mock_vws._database_matchers import AnyDatabase
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
def validate_project_state(
    *,
    request_path: str,
    request_method: str,
    database: AnyDatabase,
) -> None:
    """Validate the state of the project.

    Args:
        request_path: The path of the request.
        request_method: The HTTP method of the request.
        database: The database which the request's server keys belong to.

    Raises:
        ProjectInactiveError: The project is inactive and this endpoint does
            not work with inactive projects.
    """
    state_errors: dict[States, type[ValidatorError]] = {
        States.PROJECT_HAS_NO_API_ACCESS: ProjectHasNoApiAccessError,
        States.PROJECT_SUSPENDED: ProjectSuspendedError,
    }
    if error := state_errors.get(database.state):
        raise error

    if database.state != States.PROJECT_INACTIVE:
        return

    if (
        isinstance(database, CloudDatabase)
        and request_method == HTTPMethod.GET
        and "duplicates" not in request_path
    ):
        return

    if isinstance(database, VuMarkDatabase):
        return

    _LOGGER.warning(msg="The project is inactive.")
    raise ProjectInactiveError
