"""Tests for giving invalid JSON to endpoints.

The three cases are separate tests, rather than one test covering
every body, because each body costs a request per endpoint against
Real Vuforia and CI runs one ``ci_pattern`` per job. See
https://github.com/VWS-Python/vws-python-mock/issues/3540.
"""

from datetime import datetime, timedelta
from http import HTTPStatus
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time
from vws_auth_tools import authorization_header, rfc_1123_date

from vws_mock_contract_tests.invalid_json.helpers import assert_body_rejected
from vws_mock_contract_tests.utils import Endpoint
from vws_mock_contract_tests.utils.assertions import (
    assert_valid_date_header,
    assert_vws_failure,
)
from vws_mock_contract_tests.utils.too_many_requests import (
    handle_server_errors,
)


def test_not_json(endpoint: Endpoint) -> None:
    """Giving a body which is not JSON returns an error response."""
    assert_body_rejected(endpoint=endpoint, content=b"a")


@pytest.mark.parametrize(
    argnames="content", argvalues=[b"[]", b'"hello"', b"5", b"null", b"true"]
)
def test_not_an_object(endpoint: Endpoint, content: bytes) -> None:
    """Giving valid JSON which is not an object returns an error
    response.
    """
    assert_body_rejected(endpoint=endpoint, content=content)


def test_not_utf_8(endpoint: Endpoint) -> None:
    """Giving a JSON object which is not encoded as UTF-8 returns an
    error response.
    """
    content = '{"name": "café"}'.encode(encoding="latin-1")
    assert_body_rejected(endpoint=endpoint, content=content)


def test_empty_body(endpoint: Endpoint) -> None:
    """Giving an empty body to an endpoint which takes JSON returns an
    error response.

    The VuMark instance generation endpoint returns a bad request.
    """
    expected_status_code = HTTPStatus.BAD_REQUEST
    expected_result_code = "BadRequest"
    content = b""
    gmt = ZoneInfo(key="GMT")
    now = datetime.now(tz=gmt)
    time_to_freeze = now
    with freeze_time(time_to_freeze=time_to_freeze):
        date = rfc_1123_date()
    authorization_string = authorization_header(
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
        method=endpoint.method,
        content=content,
        content_type=endpoint.auth_header_content_type,
        date=date,
        request_path=endpoint.path_url,
    )
    new_headers = {
        **endpoint.headers,
        "Authorization": authorization_string,
        "Date": date,
        "Content-Length": str(object=len(content)),
    }
    new_endpoint = Endpoint(
        base_url=endpoint.base_url,
        path_url=endpoint.path_url,
        method=endpoint.method,
        headers=new_headers,
        data=content,
        successful_headers_result_code=endpoint.successful_headers_result_code,
        successful_headers_status_code=endpoint.successful_headers_status_code,
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
    )
    response = new_endpoint.send()
    handle_server_errors(response=response)
    assert_valid_date_header(response=response)
    assert_vws_failure(
        response=response,
        status_code=expected_status_code,
        result_code=expected_result_code,
    )


def test_invalid_json_with_skewed_time(endpoint: Endpoint) -> None:
    """Giving invalid JSON to endpoints returns error responses."""
    date_skew_minutes = 70
    content = b"a"
    gmt = ZoneInfo(key="GMT")
    now = datetime.now(tz=gmt)
    time_to_freeze = now + timedelta(minutes=date_skew_minutes)
    with freeze_time(time_to_freeze=time_to_freeze):
        date = rfc_1123_date()
    authorization_string = authorization_header(
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
        method=endpoint.method,
        content=content,
        content_type=endpoint.auth_header_content_type,
        date=date,
        request_path=endpoint.path_url,
    )
    new_headers = {
        **endpoint.headers,
        "Authorization": authorization_string,
        "Content-Length": str(object=len(content)),
        "Date": date,
    }
    new_endpoint = Endpoint(
        base_url=endpoint.base_url,
        path_url=endpoint.path_url,
        method=endpoint.method,
        headers=new_headers,
        data=content,
        successful_headers_result_code=endpoint.successful_headers_result_code,
        successful_headers_status_code=endpoint.successful_headers_status_code,
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
    )
    response = new_endpoint.send()
    handle_server_errors(response=response)
    assert_valid_date_header(response=response)
    assert_vws_failure(
        response=response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code="RequestTimeTooSkewed",
    )
