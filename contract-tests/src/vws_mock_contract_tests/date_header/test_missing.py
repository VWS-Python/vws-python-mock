"""Tests for what happens when the `Date` header is missing."""

from http import HTTPStatus

from vws_auth_tools import authorization_header

from vws_mock_contract_tests.utils import Endpoint
from vws_mock_contract_tests.utils.assertions import assert_vws_failure
from vws_mock_contract_tests.utils.too_many_requests import (
    handle_server_errors,
)


def test_no_date_header(endpoint: Endpoint) -> None:
    """
    A `BAD_REQUEST` response is returned when no `Date` header is
    given.
    """
    authorization_string = authorization_header(
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
        method=endpoint.method,
        content=endpoint.data,
        content_type=endpoint.auth_header_content_type,
        date="",
        request_path=endpoint.path_url,
    )
    new_headers: dict[str, str] = {
        **endpoint.headers,
        "Authorization": authorization_string,
    }
    _ = new_headers.pop("Date", None)
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
