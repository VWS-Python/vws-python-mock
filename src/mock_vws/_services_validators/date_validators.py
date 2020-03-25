"""
Validators of the date header to use in the mock services API.
"""

import datetime
from typing import Dict, List

import pytz
from requests import codes

from mock_vws._services_validators.exceptions import Fail, RequestTimeTooSkewed
from mock_vws.database import VuforiaDatabase


def validate_date_header_given(
    request_headers: Dict[str, str],
) -> None:
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

    if 'Date' in request_headers:
        return

    raise Fail(status_code=codes.BAD_REQUEST)


def validate_date_format(
    request_headers: Dict[str, str],
) -> None:
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

    date_header = request_headers['Date']
    date_format = '%a, %d %b %Y %H:%M:%S GMT'
    try:
        datetime.datetime.strptime(date_header, date_format)
    except ValueError:
        raise Fail(status_code=codes.BAD_REQUEST)


def validate_date_in_range(
    request_headers: Dict[str, str],
) -> None:
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

    date_from_header = datetime.datetime.strptime(
        request_headers['Date'],
        '%a, %d %b %Y %H:%M:%S GMT',
    )

    gmt = pytz.timezone('GMT')
    now = datetime.datetime.now(tz=gmt)
    date_from_header = date_from_header.replace(tzinfo=gmt)
    time_difference = now - date_from_header

    maximum_time_difference = datetime.timedelta(minutes=5)

    if abs(time_difference) >= maximum_time_difference:
        raise RequestTimeTooSkewed
