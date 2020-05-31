"""
Validators of the date header to use in the mock query API.
"""

import datetime
from typing import Dict, Set

from backports.zoneinfo import ZoneInfo

from mock_vws._query_validators.exceptions import (
    DateFormatNotValid,
    DateHeaderNotGiven,
    RequestTimeTooSkewed,
)


def validate_date_header_given(request_headers: Dict[str, str]) -> None:
    """
    Validate the date header is given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        DateHeaderNotGiven: The date is not given.
    """
    if 'Date' in request_headers:
        return

    raise DateHeaderNotGiven


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


def validate_date_format(request_headers: Dict[str, str]) -> None:
    """
    Validate the format of the date header given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        DateFormatNotValid: The date is in the wrong format.
    """
    date_header = request_headers['Date']

    for date_format in _accepted_date_formats():
        try:
            datetime.datetime.strptime(date_header, date_format)
        except ValueError:
            pass
        else:
            return

    raise DateFormatNotValid


def validate_date_in_range(request_headers: Dict[str, str]) -> None:
    """
    Validate date in the date header given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.

    Raises:
        RequestTimeTooSkewed: The date is out of range.
    """
    date_header = request_headers['Date']

    for date_format in _accepted_date_formats():
        try:
            date = datetime.datetime.strptime(date_header, date_format)
            # We could break here but that would give a coverage report that is
            # not 100%.
        except ValueError:
            pass

    gmt = ZoneInfo('GMT')
    now = datetime.datetime.now(tz=gmt)
    date_from_header = date.replace(tzinfo=gmt)
    time_difference = now - date_from_header

    maximum_time_difference = datetime.timedelta(minutes=65)

    if abs(time_difference) < maximum_time_difference:
        return

    raise RequestTimeTooSkewed
