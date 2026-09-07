"""Validators for database IDs given in request paths."""

import logging

from beartype import beartype

from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import (
    AuthenticationFailureError,
)
from mock_vws.database import CloudDatabase

_LOGGER = logging.getLogger(name=__name__)
# The index of the database ID in
# ``/imagetargets/databases/{database_id}/reports/recoCounts``, split on "/".
_DATABASE_ID_PATH_INDEX = 3


@beartype
def validate_database_id_matches_keys(*, context: ValidatorContext) -> None:
    """Validate a database ID given in the request path.

    The ID must be the ID of the database which the request's server keys
    belong to.

    Args:
        context: The context of the request.

    Raises:
        AuthenticationFailureError: The request path names a database other
            than the one which the request's server keys belong to.
    """
    given_database_id = context.request_path.split(sep="/")[
        _DATABASE_ID_PATH_INDEX
    ]
    if (
        isinstance(context.database, CloudDatabase)
        and context.database.database_id == given_database_id
    ):
        return

    _LOGGER.warning(
        'The database ID "%s" is not the ID of the database which the '
        "request's server keys belong to.",
        given_database_id,
    )
    raise AuthenticationFailureError
