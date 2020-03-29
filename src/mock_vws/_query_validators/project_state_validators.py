"""
Validators for the project state.
"""

import uuid
from typing import Dict, List

import wrapt
from requests import codes

from mock_vws._constants import ResultCodes
from mock_vws._database_matchers import get_database_matching_client_keys
from mock_vws.database import VuforiaDatabase
from mock_vws.states import States


@wrapt.decorator
def validate_project_state(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the state of the project.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `FORBIDDEN` response with an InactiveProject result code if the
        project is inactive.
    """
    database = get_database_matching_client_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    assert isinstance(database, VuforiaDatabase)
    if database.state != States.PROJECT_INACTIVE:
        return

    context.status_code = codes.FORBIDDEN
    transaction_id = uuid.uuid4().hex
    result_code = ResultCodes.INACTIVE_PROJECT.value

    # The response has an unusual format of separators, so we construct it
    # manually.
    return (
        '{"transaction_id": '
        f'"{transaction_id}",'
        f'"result_code":"{result_code}"'
        '}'
    )
