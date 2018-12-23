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


@wrapt.decorator
def validate_content_length_header(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the ``Content-Length`` header.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
    """
    request, context = args
    given_content_length = request.headers.get('Content-Length')
    if not given_content_length:
        return wrapped(*args, **kwargs)

    try:
        int(given_content_length)
    except ValueError:
        context.status_code = codes.BAD_REQUEST
        context.headers = {'Connection': 'Close'}
        return ''

    body_length = len(request.body if request.body else '')
    given_content_length_value = int(given_content_length)
    if given_content_length_value > body_length:
        context.status_code = codes.GATEWAY_TIMEOUT
        context.headers = {'Connection': 'keep-alive'}
        return ''

    if given_content_length_value < body_length:
        context.status_code = codes.UNAUTHORIZED
        context.headers['WWW-Authenticate'] = 'VWS'
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.AUTHENTICATION_FAILURE.value,
        }
        return json_dump(body)

    return wrapped(*args, **kwargs)
