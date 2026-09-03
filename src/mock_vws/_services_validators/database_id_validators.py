"""Validators for database IDs given in request paths."""

import logging
import re

from beartype import beartype

from mock_vws._database_matchers import AnyDatabase
from mock_vws._mock_common import RECO_COUNTS_REPORT_PATH_PATTERN
from mock_vws._services_validators.exceptions import (
    AuthenticationFailureError,
)
from mock_vws.database import CloudDatabase

_LOGGER = logging.getLogger(name=__name__)
# The index of the database ID in
# ``/imagetargets/databases/{database_id}/reports/recoCounts``, split on "/".
_DATABASE_ID_PATH_INDEX = 3


@beartype
def validate_database_id_matches_keys(
    *,
    request_path: str,
    database: AnyDatabase,
) -> None:
    """Validate a database ID given in the request path.

    The ID must be the ID of the database which the request's server keys
    belong to.

    Args:
        request_path: The path of the request.
        database: The database which the request's server keys belong to.

    Raises:
        AuthenticationFailureError: The request path names a database other
            than the one which the request's server keys belong to.
    """
    if not re.fullmatch(
        pattern=RECO_COUNTS_REPORT_PATH_PATTERN,
        string=request_path,
    ):
        return

    given_database_id = request_path.split(sep="/")[_DATABASE_ID_PATH_INDEX]
    if (
        isinstance(database, CloudDatabase)
        and database.database_id == given_database_id
    ):
        return

    _LOGGER.warning(
        'The database ID "%s" is not the ID of the database which the '
        "request's server keys belong to.",
        given_database_id,
    )
    raise AuthenticationFailureError
