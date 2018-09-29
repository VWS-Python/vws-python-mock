"""
Authorization validators to use in the mock query API.
"""

from typing import Any, Callable, Dict, Tuple

import wrapt
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from .._mock_common import get_database_matching_client_keys


@wrapt.decorator
def validate_auth_header_exists(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args
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
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args

    header = request.headers['Authorization']
    parts = header.split(' ')
    if len(parts) == 2 and len(parts[1]):
        return wrapped(*args, **kwargs)

    context.status_code = codes.UNAUTHORIZED
    text = 'Malformed authorization header.'
    content_type = 'text/plain; charset=ISO-8859-1'
    context.headers['Content-Type'] = content_type
    context.headers['WWW-Authenticate'] = 'VWS'
    return text

@wrapt.decorator
def validate_auth_header_has_signature(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args

    header = request.headers['Authorization']
    if header.count(':') == 1 and len(header.split(':')[1]):
        return wrapped(*args, **kwargs)

    context.status_code = codes.INTERNAL_SERVER_ERROR
    text = 'Malformed authorization header.'
    content_type = 'text/html; charset=ISO-8859-1'
    context.headers['Content-Type'] = content_type
    cache_control = 'must-revalidate,no-cache,no-store'
    context.headers['Cache-Control'] = cache_control
    return text

@wrapt.decorator
def validate_authorization(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args

    database = get_database_matching_client_keys(
        request=request,
        databases=instance.databases,
    )

    if database is not None:
        return wrapped(*args, **kwargs)

    context.status_code = codes.UNAUTHORIZED
    text = 'Malformed authorization header.'
    content_type = 'text/plain; charset=ISO-8859-1'
    context.headers['Content-Type'] = content_type
    context.headers['WWW-Authenticate'] = 'VWS'
    return text
