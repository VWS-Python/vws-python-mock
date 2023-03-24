"""
Validators of the date header to use in the mock services API.
"""

import datetime
import logging
from http import HTTPStatus
from zoneinfo import ZoneInfo

from mock_vws._services_validators.exceptions import Fail, RequestTimeTooSkewed

_LOGGER = logging.getLogger(__name__)


def validate_date_header_given(request_headers: dict[str, str]) -> None:
    """
    Validate the date header is given to a VWS endpoint.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        Fail: The date is not given.
    """
    if "Date" in request_headers:
        return

    _LOGGER.warning(msg="The date header is not given.")
    raise Fail(status_code=HTTPStatus.BAD_REQUEST)


def validate_date_format(request_headers: dict[str, str]) -> None:
    """
    Validate the format of the date header given to a VWS endpoint.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        Fail: The date is in the wrong format.
    """
    date_header = request_headers["Date"]
    date_format = "%a, %d %b %Y %H:%M:%S GMT"
    try:
        datetime.datetime.strptime(date_header, date_format).astimezone()
    except ValueError as exc:
        _LOGGER.warning(msg="The date header is in the wrong format.")
        raise Fail(status_code=HTTPStatus.BAD_REQUEST) from exc


def validate_date_in_range(request_headers: dict[str, str]) -> None:
    """
    Validate the date header given to a VWS endpoint is in range.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        RequestTimeTooSkewed: The date is out of range.
    """
    gmt = ZoneInfo("GMT")
    date_from_header = datetime.datetime.strptime(
        request_headers["Date"],
        "%a, %d %b %Y %H:%M:%S GMT",
    ).replace(tzinfo=gmt)

    now = datetime.datetime.now(tz=gmt)
    time_difference = now - date_from_header

    maximum_time_difference = datetime.timedelta(minutes=5)

    if abs(time_difference) >= maximum_time_difference:
        _LOGGER.warning(msg="The date header is out of range.")
        raise RequestTimeTooSkewed
