"""
Validators for given target IDs.
"""
import uuid
from typing import Any, Callable, Dict, Tuple

import wrapt
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import json_dump
from mock_vws.database import VuforiaDatabase


@wrapt.decorator
def validate_target_id_exists(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args

    split_path = request.path.split('/')

    if len(split_path) == 2:
        return wrapped(*args, **kwargs)

    target_id = split_path[-1]
    database = get_database_matching_server_keys(
        request_headers=request.headers,
        request_body=request.body,
        request_method=request.method,
        request_path=request.path,
        databases=instance.databases,
    )

    assert isinstance(database, VuforiaDatabase)

    try:
        [_] = [
            target for target in database.targets
            if target.target_id == target_id and not target.delete_date
        ]
    except ValueError:
        body: Dict[str, str] = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.UNKNOWN_TARGET.value,
        }
        context.status_code = codes.NOT_FOUND
        return json_dump(body)

    return wrapped(*args, **kwargs)
