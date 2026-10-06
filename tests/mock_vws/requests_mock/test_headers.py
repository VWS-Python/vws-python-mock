"""Tests for headers through the `requests-mock` backend."""

import datetime
import email.utils

import requests
from freezegun import freeze_time

from mock_vws import MockVWS


def test_date_changes() -> None:
    """
    The date that the response is sent is in the response Date
    header.
    """
    new_year = 2012
    new_time = datetime.datetime(
        year=new_year,
        month=1,
        day=1,
        tzinfo=datetime.UTC,
    )
    with MockVWS(), freeze_time(time_to_freeze=new_time):
        response = requests.get(
            url="https://vws.vuforia.com/summary",
            timeout=30,
        )

    date_response = response.headers["Date"]
    date_from_response = email.utils.parsedate(data=date_response)
    assert date_from_response is not None
    year = date_from_response[0]
    assert year == new_year
