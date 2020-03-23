"""
Input validators to use in the mock.
"""

import numbers
import uuid
from json.decoder import JSONDecodeError
from typing import Any, Callable, Dict, Set, Tuple

import wrapt
from requests import codes
from requests_mock import POST, PUT
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import json_dump
from mock_vws.database import VuforiaDatabase
from mock_vws.states import States


@wrapt.decorator
def validate_active_flag(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the active flag data given to the endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response with a FAIL result code if there is
        active flag data given to the endpoint which is not either a Boolean or
        NULL.
    """
    request, context = args

    if not request.text:
        return wrapped(*args, **kwargs)

    if 'active_flag' not in request.json():
        return wrapped(*args, **kwargs)

    active_flag = request.json().get('active_flag')

    if active_flag is None or isinstance(active_flag, bool):
        return wrapped(*args, **kwargs)

    context.status_code = codes.BAD_REQUEST
    body: Dict[str, str] = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body)


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
        A `FORBIDDEN` response with a PROJECT_INACTIVE result code if the
        project is inactive.
    """
    request, context = args

    database = get_database_matching_server_keys(
        request_headers=request.headers,
        request_body=request.body,
        request_method=request.method,
        request_path=request.path,
        databases=instance.databases,
    )

    assert isinstance(database, VuforiaDatabase)
    if database.state != States.PROJECT_INACTIVE:
        return wrapped(*args, **kwargs)

    if request.method == 'GET' and 'duplicates' not in request.path:
        return wrapped(*args, **kwargs)

    context.status_code = codes.FORBIDDEN

    body: Dict[str, str] = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.PROJECT_INACTIVE.value,
    }
    return json_dump(body)


@wrapt.decorator
def validate_not_invalid_json(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate that there is either no JSON given or the JSON given is valid.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response with a FAIL result code if there is invalid
        JSON given to a POST or PUT request.
        A `BAD_REQUEST` with empty text if there is data given to another
        request type.
    """
    request, context = args

    if not request.body:
        return wrapped(*args, **kwargs)

    if request.method not in (POST, PUT):
        context.status_code = codes.BAD_REQUEST
        context.headers.pop('Content-Type')
        return ''

    try:
        request.json()
    except JSONDecodeError:
        context.status_code = codes.BAD_REQUEST
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        return json_dump(body)

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_width(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the width argument given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the width is given and is not a positive
        number.
    """
    request, context = args

    if not request.text:
        return wrapped(*args, **kwargs)

    if 'width' not in request.json():
        return wrapped(*args, **kwargs)

    width = request.json().get('width')

    width_is_number = isinstance(width, numbers.Number)
    width_positive = width_is_number and width > 0

    if not width_positive:
        context.status_code = codes.BAD_REQUEST
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        return json_dump(body)

    return wrapped(*args, **kwargs)


def validate_keys(
    mandatory_keys: Set[str],
    optional_keys: Set[str],
) -> Callable:
    """
    Args:
        mandatory_keys: Keys required by the endpoint.
        optional_keys: Keys which are not required by the endpoint but which
            are allowed.

    Returns:
        A wrapper function to validate that the keys given to the endpoint are
            all allowed and that the mandatory keys are given.
    """

    @wrapt.decorator
    def wrapper(
        wrapped: Callable[..., str],
        instance: Any,  # pylint: disable=unused-argument
        args: Tuple[_RequestObjectProxy, _Context],
        kwargs: Dict,
    ) -> str:
        """
        Validate the request keys given to a VWS endpoint.

        Returns:
            The result of calling the endpoint.
            A `BAD_REQUEST` error if any keys are not allowed, or if any
            required keys are missing.

        Args:
            wrapped: An endpoint function for `requests_mock`.
            instance: The class that the endpoint function is in.
            args: The arguments given to the endpoint function.
            kwargs: The keyword arguments given to the endpoint function.
        """
        request, context = args
        allowed_keys = mandatory_keys.union(optional_keys)

        if request.text is None and not allowed_keys:
            return wrapped(*args, **kwargs)

        given_keys = set(request.json().keys())
        all_given_keys_allowed = given_keys.issubset(allowed_keys)
        all_mandatory_keys_given = mandatory_keys.issubset(given_keys)

        if all_given_keys_allowed and all_mandatory_keys_given:
            return wrapped(*args, **kwargs)

        context.status_code = codes.BAD_REQUEST
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        return json_dump(body)

    wrapper_func: Callable[..., Any] = wrapper
    return wrapper_func
