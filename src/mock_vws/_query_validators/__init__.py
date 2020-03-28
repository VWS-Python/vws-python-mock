"""
Input validators to use in the mock query API.
"""

import cgi
import io
import uuid
from typing import Any, Callable, Dict, Tuple

import wrapt
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws.database import VuforiaDatabase
from mock_vws.states import States

from mock_vws._constants import ResultCodes
from mock_vws._database_matchers import get_database_matching_client_keys
from mock_vws._mock_common import parse_multipart


@wrapt.decorator
def validate_content_type_header(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the ``Content-Type`` header.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An ``UNSUPPORTED_MEDIA_TYPE`` response if the ``Content-Type`` header
        main part is not 'multipart/form-data'.
        A ``BAD_REQUEST`` response if the ``Content-Type`` header does not
        contain a boundary which is in the request body.
    """
    request, context = args

    main_value, pdict = cgi.parse_header(request.headers['Content-Type'])
    if main_value != 'multipart/form-data':
        context.status_code = codes.UNSUPPORTED_MEDIA_TYPE
        context.headers.pop('Content-Type')
        return ''

    if 'boundary' not in pdict:
        context.status_code = codes.BAD_REQUEST
        context.headers['Content-Type'] = 'text/html;charset=UTF-8'
        return (
            'java.io.IOException: RESTEASY007550: '
            'Unable to get boundary for multipart'
        )

    if pdict['boundary'].encode() not in request.body:
        context.status_code = codes.BAD_REQUEST
        context.headers['Content-Type'] = 'text/html;charset=UTF-8'
        return (
            'java.lang.RuntimeException: RESTEASY007500: '
            'Could find no Content-Disposition header within part'
        )

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_accept_header(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the accept header.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `NOT_ACCEPTABLE` response if the Accept header is given and is not
        'application/json' or '*/*'.
    """
    request, context = args

    accept = request.headers.get('Accept')
    if accept in ('application/json', '*/*', None):
        return wrapped(*args, **kwargs)

    context.headers.pop('Content-Type')
    context.status_code = codes.NOT_ACCEPTABLE
    return ''


@wrapt.decorator
def validate_extra_fields(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate that the no unknown fields are given.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A ``BAD_REQUEST`` response if extra fields are given.
    """
    request, context = args
    body_file = io.BytesIO(request.body)

    _, pdict = cgi.parse_header(request.headers['Content-Type'])
    parsed = parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    known_parameters = {'image', 'max_num_results', 'include_target_data'}

    if not parsed.keys() - known_parameters:
        return wrapped(*args, **kwargs)

    context.status_code = codes.BAD_REQUEST
    return 'Unknown parameters in the request.'
