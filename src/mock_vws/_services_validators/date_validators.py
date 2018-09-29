"""
Validators of the date header to use in the mock services API.
"""

import datetime
import uuid
from typing import Any, Callable, Dict, Tuple

import pytz
import wrapt
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump


@wrapt.decorator
def validate_date_header_given(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the date header is given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the date is not given.
    """
    request, context = args

    if 'Date' in request.headers:
        return wrapped(*args, **kwargs)

    context.status_code = codes.BAD_REQUEST
    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body)


@wrapt.decorator
def validate_date_format(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the format of the date header given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the date is in the wrong format.
        A `FORBIDDEN` response if the date is out of range.
    """
    request, context = args

    date_header = request.headers['Date']
    date_format = '%a, %d %b %Y %H:%M:%S GMT'
    try:
        datetime.datetime.strptime(date_header, date_format)
    except ValueError:
        context.status_code = codes.BAD_REQUEST
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        return json_dump(body)

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_date_in_range(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the date header given to a VWS endpoint is in range.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `FORBIDDEN` response if the date is out of range.
    """
    request, context = args

    date_from_header = datetime.datetime.strptime(
        request.headers['Date'],
        '%a, %d %b %Y %H:%M:%S GMT',
    )

    gmt = pytz.timezone('GMT')
    now = datetime.datetime.now(tz=gmt)
    date_from_header = date_from_header.replace(tzinfo=gmt)
    time_difference = now - date_from_header

    maximum_time_difference = datetime.timedelta(minutes=5)

    if abs(time_difference) >= maximum_time_difference:
        context.status_code = codes.FORBIDDEN

        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.REQUEST_TIME_TOO_SKEWED.value,
        }
        return json_dump(body)

    return wrapped(*args, **kwargs)
