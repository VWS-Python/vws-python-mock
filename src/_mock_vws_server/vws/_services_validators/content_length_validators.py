"""
Content-Length header validators to use in the mock.
"""

import uuid
from typing import Any, Callable, Dict, Tuple

import wrapt
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from .._constants import ResultCodes
from .._mock_common import json_dump
from flask import request


@wrapt.decorator
def validate_content_length_header_is_int(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the ``Content-Length`` header is an integer.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A ``BAD_REQUEST`` response if the content length header is not an
        integer.
    """

    body_length = len(request.data if request.data else '')
    given_content_length = request.headers.get('Content-Length', body_length)

    try:
        int(given_content_length)
    except ValueError:
        # TODO construct response
        # context.headers = {'Connection': 'Close'}
        return '', codes.BAD_REQUEST

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_content_length_header_not_too_large(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the ``Content-Length`` header is not too large.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A ``GATEWAY_TIMEOUT`` response if the given content length header says
        that the content length is greater than the body length.
    """

    body_length = len(request.data if request.data else '')
    given_content_length = request.headers.get('Content-Length', body_length)
    given_content_length_value = int(given_content_length)
    if given_content_length_value > body_length:
        # TODO construct a response object
        # context.headers = {'Connection': 'keep-alive'}
        return '', codes.GATEWAY_TIMEOUT

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_content_length_header_not_too_small(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the ``Content-Length`` header is not too small.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An ``UNAUTHORIZED`` response if the given content length header says
        that the content length is smaller than the body length.
    """

    body_length = len(request.data if request.data else '')
    given_content_length = request.headers.get('Content-Length', body_length)
    given_content_length_value = int(given_content_length)

    if given_content_length_value < body_length:
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.AUTHENTICATION_FAILURE.value,
        }
        return json_dump(body), codes.UNAUTHORIZED

    return wrapped(*args, **kwargs)
