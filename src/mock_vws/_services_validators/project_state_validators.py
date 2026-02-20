"""Validators for the project state."""

import logging
from collections.abc import Iterable, Mapping
from http import HTTPMethod

from beartype import beartype

from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._services_validators.exceptions import ProjectInactiveError
from mock_vws.database import CloudDatabase
from mock_vws.states import States
from mock_vws.target_manager import AnyDatabase

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

    if not isinstance(database, CloudDatabase):
        return

    if database.state != States.PROJECT_INACTIVE:
        return

    if request_method == HTTPMethod.GET and "duplicates" not in request_path:
        return

    _LOGGER.warning(msg="The project is inactive.")
    raise ProjectInactiveError
