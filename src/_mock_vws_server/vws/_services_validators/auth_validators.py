"""
Authorization header validators to use in the mock.
"""

import uuid
from typing import Any, Callable, Dict, Tuple

import wrapt
from flask import request
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import json_dump


@wrapt.decorator
def validate_auth_header_exists(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate that there is an authorization header given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNAUTHORIZED` response if there is no "Authorization" header.
    """

    if 'Authorization' in request.headers:
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.AUTHENTICATION_FAILURE.value,
    }
    return json_dump(body), codes.UNAUTHORIZED


@wrapt.decorator
def validate_access_key_exists(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the authorization header includes an access key for a database.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An ``UNAUTHORIZED`` response if the access key is unknown.
    """

    header = request.headers['Authorization']
    first_part, _ = header.split(':')
    _, access_key = first_part.split(' ')
    for database in instance.databases:
        if access_key == database.server_access_key:
            return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body), codes.BAD_REQUEST


@wrapt.decorator
def validate_auth_header_has_signature(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the authorization header includes a signature.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An ``UNAUTHORIZED`` response if the "Authorization" header is not as
        expected.
    """

    header = request.headers['Authorization']
    if header.count(':') == 1 and header.split(':')[1]:
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body), codes.BAD_REQUEST


@wrapt.decorator
def validate_authorization(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the authorization header given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the "Authorization" header is not as
        expected.
    """

    database = get_database_matching_server_keys(
        request=request,
        databases=instance.databases,
    )

    if database is not None:
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.AUTHENTICATION_FAILURE.value,
    }
    return json_dump(body), codes.UNAUTHORIZED
