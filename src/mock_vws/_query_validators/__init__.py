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

from .._constants import ResultCodes
from .._mock_common import get_database_matching_client_keys, parse_multipart


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


@wrapt.decorator
def validate_project_state(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args

    database = get_database_matching_client_keys(
        request=request,
        databases=instance.databases,
    )

    assert isinstance(database, VuforiaDatabase)
    if database.state != States.PROJECT_INACTIVE:
        return wrapped(*args, **kwargs)

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


@wrapt.decorator
def validate_max_num_results(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the ``max_num_results`` field is either an integer within range or
    not given.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the ``max_num_results`` field is either not
        an integer, or an integer out of range.
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
    [max_num_results] = parsed.get('max_num_results', ['1'])
    invalid_type_error = (
        f"Invalid value '{max_num_results}' in form data part "
        "'max_result'. "
        'Expecting integer value in range from 1 to 50 (inclusive).'
    )

    try:
        max_num_results_int = int(max_num_results)
    except ValueError:
        context.status_code = codes.BAD_REQUEST
        return invalid_type_error

    java_max_int = 2147483647
    if max_num_results_int > java_max_int:
        context.status_code = codes.BAD_REQUEST
        return invalid_type_error

    if max_num_results_int < 1 or max_num_results_int > 50:
        context.status_code = codes.BAD_REQUEST
        out_of_range_error = (
            f'Integer out of range ({max_num_results_int}) in form data part '
            "'max_result'. Accepted range is from 1 to 50 (inclusive)."
        )
        return out_of_range_error

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_include_target_data(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the ``include_target_data`` field is either an accepted value or
    not given.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the ``include_target_data`` field is not an
        accepted value.
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

    [include_target_data] = parsed.get('include_target_data', ['top'])
    include_target_data = include_target_data.lower()
    allowed_included_target_data = {'top', 'all', 'none'}
    if include_target_data in allowed_included_target_data:
        return wrapped(*args, **kwargs)

    unexpected_target_data_message = (
        f"Invalid value '{include_target_data}' in form data part "
        "'include_target_data'. "
        "Expecting one of the (unquoted) string values 'all', 'none' or 'top'."
    )
    context.status_code = codes.BAD_REQUEST
    return unexpected_target_data_message


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
        context.headers['Content-Type'] = 'text/html'
        return (
            'java.io.IOException: RESTEASY007550: '
            'Unable to get boundary for multipart'
        )

    if pdict['boundary'].encode() not in request.body:
        context.status_code = codes.BAD_REQUEST
        context.headers['Content-Type'] = 'text/html'
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
