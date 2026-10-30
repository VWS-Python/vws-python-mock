"""Shared helpers for invalid json tests."""

from datetime import datetime
from http import HTTPStatus
from zoneinfo import ZoneInfo

from beartype import beartype
from freezegun import freeze_time
from vws_auth_tools import authorization_header, rfc_1123_date

from vws_mock_contract_tests.utils import Endpoint
from vws_mock_contract_tests.utils.assertions import (
    assert_valid_date_header,
    assert_vws_failure,
)
from vws_mock_contract_tests.utils.too_many_requests import (
    handle_server_errors,
)


@beartype
def assert_body_rejected(*, endpoint: Endpoint, content: bytes) -> None:
    """Send the given body to the given endpoint and assert that it is
    rejected.

    Args:
        endpoint: The endpoint to send the body to.
        content: The body to send, which is not a JSON object encoded as
            UTF-8.
    """
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
    expected_result_code = "BadRequest"
    assert_vws_failure(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code=expected_result_code,
    )
