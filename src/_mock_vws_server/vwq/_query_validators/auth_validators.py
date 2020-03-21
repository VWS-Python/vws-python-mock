"""
Authorization validators to use in the mock query API.
"""

import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

import wrapt
from flask import request
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from ...vws._databases import get_all_databases
from .._constants import ResultCodes
from .._database_matchers import get_database_matching_client_keys


@wrapt.decorator
def validate_auth_header_exists(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate that there is an authorization header given to the query endpoint.

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

    context.status_code = codes.UNAUTHORIZED
    text = 'Authorization header missing.'
    content_type = 'text/plain; charset=ISO-8859-1'
    context.headers['Content-Type'] = content_type
    context.headers['WWW-Authenticate'] = 'VWS'
    return text


@wrapt.decorator
def validate_auth_header_number_of_parts(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the authorization header includes text either side of a space.

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
    parts = header.split(' ')
    if len(parts) == 2 and parts[1]:
        return wrapped(*args, **kwargs)

    context.status_code = codes.UNAUTHORIZED
    text = 'Malformed authorization header.'
    content_type = 'text/plain; charset=ISO-8859-1'
    context.headers['Content-Type'] = content_type
    context.headers['WWW-Authenticate'] = 'VWS'
    return text


@wrapt.decorator
def validate_client_key_exists(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the authorization header includes a client key for a database.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An ``UNAUTHORIZED`` response if the client key is unknown.
    """

    header = request.headers['Authorization']
    first_part, _ = header.split(':')
    _, access_key = first_part.split(' ')
    databases = get_all_databases()
    for database in databases:
        if access_key == database.client_access_key:
            return wrapped(*args, **kwargs)

    context.status_code = codes.UNAUTHORIZED
    context.headers['WWW-Authenticate'] = 'VWS'
    transaction_id = uuid.uuid4().hex
    result_code = ResultCodes.AUTHENTICATION_FAILURE.value
    text = (
        '{"transaction_id":'
        f'"{transaction_id}",'
        f'"result_code":"{result_code}"'
        '}'
    )
    return text


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

    # context.status_code = codes.INTERNAL_SERVER_ERROR
    current_parent = Path(__file__).parent
    resources = current_parent / 'resources'
    known_response = resources / 'query_out_of_bounds_response'
    content_type = 'text/html; charset=ISO-8859-1'
    # TODO
    # context.headers['Content-Type'] = content_type
    cache_control = 'must-revalidate,no-cache,no-store'
    # context.headers['Cache-Control'] = cache_control
    return known_response.read_text(), codes.INTERNAL_SERVER_ERROR, {
        'Content-Type': content_type,
        'Cache-Control': cache_control,
    }


@wrapt.decorator
def validate_authorization(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the authorization header given to the query endpoint.

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

    databases = get_all_databases()
    database = get_database_matching_client_keys(
        request_headers=request.headers,
        request_body=request.input_stream.getvalue(),
        request_method=request.method,
        request_path=request.path,
        databases=databases,
    )

    if database is not None:
        return wrapped(*args, **kwargs)

    # TODO
    # context.status_code = codes.UNAUTHORIZED
    # TODO
    # context.headers['WWW-Authenticate'] = 'VWS'
    transaction_id = uuid.uuid4().hex
    result_code = ResultCodes.AUTHENTICATION_FAILURE.value
    text = (
        '{"transaction_id":'
        f'"{transaction_id}",'
        f'"result_code":"{result_code}"'
        '}'
    )
    return text, codes.UNAUTHORIZED, {'WWW-Authenticate': 'VWS'}
