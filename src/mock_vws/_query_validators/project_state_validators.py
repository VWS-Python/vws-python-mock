"""Validators for the project state."""

import logging

from beartype import beartype

from mock_vws._query_validators.exceptions import InactiveProjectError
from mock_vws.database import CloudDatabase
from mock_vws.states import States

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_project_state(*, database: CloudDatabase) -> None:
    """Validate the state of the project.

    Args:
        database: The database which the request's client keys belong to.

    Raises:
        InactiveProjectError: The project is inactive.
    """
    if database.state != States.PROJECT_INACTIVE:
        return

    _LOGGER.warning(msg="The project is inactive.")
    raise InactiveProjectError
