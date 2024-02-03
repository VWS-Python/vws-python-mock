"""
Validators for given target IDs.
"""

import logging

from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._services_validators.exceptions import UnknownTarget
from mock_vws.database import VuforiaDatabase

_LOGGER = logging.getLogger(__name__)


def validate_target_id_exists(
    request_path: str,
    request_headers: dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: set[VuforiaDatabase],
) -> None:
    """
    Validate that if a target ID is given, it exists in the database matching
    the request.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Raises:
        UnknownTarget: There are no matching targets for a given target ID.
    """
    split_path = request_path.split("/")

    request_path_no_target_id_length = 2
    if len(split_path) == request_path_no_target_id_length:
        return

    target_id = split_path[-1]
    database = get_database_matching_server_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    try:
        (_,) = (
            target
            for target in database.not_deleted_targets
            if target.target_id == target_id
        )
    except ValueError as exc:
        _LOGGER.warning('The target ID "%s" does not exist.', target_id)
        raise UnknownTarget from exc
