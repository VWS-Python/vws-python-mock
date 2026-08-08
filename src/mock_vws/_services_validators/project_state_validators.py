"""Validators for the project state."""

import logging
from http import HTTPMethod
from typing import TYPE_CHECKING

from beartype import beartype

from mock_vws._database_matchers import (
    AnyDatabase,
    get_database_matching_server_keys,
)
from mock_vws._services_validators.exceptions import (
    ProjectHasNoApiAccessError,
    ProjectInactiveError,
    ProjectSuspendedError,
    ValidatorError,
)
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.states import States

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_project_state(
    *,
    request_path: str,
    request_headers: Mapping[str, str],
    request_body: bytes,
    request_method: str,
    databases: Iterable[AnyDatabase],
) -> None:
    """Validate the state of the project.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Raises:
        ProjectInactiveError: The project is inactive and this endpoint does
            not work with inactive projects.
    """
    database = get_database_matching_server_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

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
