"""
Validators for given target IDs.
"""
from typing import Dict, List

from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._services_validators.exceptions import UnknownTarget
from mock_vws.database import VuforiaDatabase


def validate_target_id_exists(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate that if a target ID is given, it exists in the database matching
    the request.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `NOT_FOUND` response if there is no matching target.
    """
    split_path = request_path.split('/')

    if len(split_path) == 2:
        return

    target_id = split_path[-1]
    database = get_database_matching_server_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    assert isinstance(database, VuforiaDatabase)

    try:
        [_] = [
            target for target in database.targets
            if target.target_id == target_id and not target.delete_date
        ]
    except ValueError:
        raise UnknownTarget
