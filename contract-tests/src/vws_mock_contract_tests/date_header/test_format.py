"""
Tests for what happens when the `Date` header is not in the expected
format.
"""

from datetime import datetime
from http import HTTPStatus
from zoneinfo import ZoneInfo

from freezegun import freeze_time
from vws_auth_tools import authorization_header

from vws_mock_contract_tests.utils import Endpoint
from vws_mock_contract_tests.utils.assertions import assert_vws_failure
from vws_mock_contract_tests.utils.too_many_requests import (
    handle_server_errors,
)


def test_incorrect_date_format(endpoint: Endpoint) -> None:
    """A `BAD_REQUEST` response is returned when the date given in the
    date
    header is not in the expected format (RFC 1123) to VWS API.

    An `UNAUTHORIZED` response is returned to the VWQ API.
    """
    gmt = ZoneInfo(key="GMT")
    with freeze_time(time_to_freeze=datetime.now(tz=gmt)):
        now = datetime.now(tz=gmt)
        date_incorrect_format = now.strftime(format="%a %b %d %H:%M:%S")
    authorization_string = authorization_header(
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
        method=endpoint.method,
        content=endpoint.data,
        content_type=endpoint.auth_header_content_type,
        date=date_incorrect_format,
        request_path=endpoint.path_url,
    )
    new_headers = {
        **endpoint.headers,
        "Authorization": authorization_string,
        "Date": date_incorrect_format,
    }
    new_endpoint = Endpoint(
        base_url=endpoint.base_url,
        path_url=endpoint.path_url,
        method=endpoint.method,
        headers=new_headers,
        data=endpoint.data,
        successful_headers_result_code=endpoint.successful_headers_result_code,
        successful_headers_status_code=endpoint.successful_headers_status_code,
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
    )
    response = new_endpoint.send()
    handle_server_errors(response=response)
    assert_vws_failure(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code="Fail",
    )
