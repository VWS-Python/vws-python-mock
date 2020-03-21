"""
Validators of the date header to use in the mock query API.
"""

import datetime
import uuid
from typing import Any, Callable, Dict, Set, Tuple

import pytz
import wrapt
from flask import request
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from .._constants import ResultCodes
from .._mock_common import json_dump


@wrapt.decorator
def validate_date_header_given(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the date header is given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the date is not given.
    """

    if 'Date' in request.headers:
        return wrapped(*args, **kwargs)

    content_type = 'text/plain; charset=ISO-8859-1'
    # TODO remove legacy
    # context.headers['Content-Type'] = content_type
    return 'Date header required.', codes.BAD_REQUEST, {
        'Content-Type': content_type,
    }


def _accepted_date_formats() -> Set[str]:
    """
    Return all known accepted date formats.

    We expect that more formats than this will be accepted.
    These are the accepted ones we know of at the time of writing.
    """
    known_accepted_formats = {
        '%a, %b %d %H:%M:%S %Y',
        '%a %b %d %H:%M:%S %Y',
        '%a, %d %b %Y %H:%M:%S',
        '%a %d %b %Y %H:%M:%S',
    }

    known_accepted_formats = known_accepted_formats.union(
        set(date_format + ' GMT' for date_format in known_accepted_formats),
    )

    return known_accepted_formats


@wrapt.decorator
def validate_date_format(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate the format of the date header given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNAUTHORIZED` response if the date is in the wrong format.
    """

    date_header = request.headers['Date']

    for date_format in _accepted_date_formats():
        try:
            datetime.datetime.strptime(date_header, date_format)
        except ValueError:
            pass
        else:
            return wrapped(*args, **kwargs)

    # context.status_code = codes.UNAUTHORIZED
    # TODO remove this legacy
    # context.headers['WWW-Authenticate'] = 'VWS'
    text = 'Malformed date header.'
    content_type = 'text/plain; charset=ISO-8859-1'
    # TODO remove this legacy
    # context.headers['Content-Type'] = content_type
    return text, codes.UNAUTHORIZED, {
        'Content-Type': content_type,
        'WWW-Authenticate': 'VWS',
    }


@wrapt.decorator
def validate_date_in_range(
    wrapped: Callable[..., Tuple[str, int]],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> Tuple[str, int]:
    """
    Validate date in the date header given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `FORBIDDEN` response if the date is out of range.
    """

    date_header = request.headers['Date']

    for date_format in _accepted_date_formats():
        try:
            date = datetime.datetime.strptime(date_header, date_format)
            # We could break here but that would give a coverage report that is
            # not 100%.
        except ValueError:
            pass

    gmt = pytz.timezone('GMT')
    now = datetime.datetime.now(tz=gmt)
    date_from_header = date.replace(tzinfo=gmt)
    time_difference = now - date_from_header

    maximum_time_difference = datetime.timedelta(minutes=65)

    if abs(time_difference) < maximum_time_difference:
        return wrapped(*args, **kwargs)

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.REQUEST_TIME_TOO_SKEWED.value,
    }
    return json_dump(body), codes.FORBIDDEN
