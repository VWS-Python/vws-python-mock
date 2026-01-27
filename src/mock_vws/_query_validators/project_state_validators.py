"""Validators for the project state."""

import logging
from typing import TYPE_CHECKING

from beartype import beartype

from mock_vws._database_matchers import get_database_matching_client_keys
from mock_vws._query_validators.exceptions import InactiveProjectError
from mock_vws.states import States

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from mock_vws.database import VuforiaDatabase

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_project_state(
    request_path: str,
    request_headers: Mapping[str, str],
    request_body: bytes,
    request_method: str,
    databases: Iterable[VuforiaDatabase],
) -> None:
    """Validate the state of the project.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Raises:
        InactiveProjectError: The project is inactive.
    """
    database = get_database_matching_client_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    if database.state != States.PROJECT_INACTIVE:
        return

    _LOGGER.warning(msg="The project is inactive.")
    raise InactiveProjectError
