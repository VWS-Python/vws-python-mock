"""
Tests for what happens when the `Authorization` header is not as
expected.
"""

from http import HTTPStatus

from vws_auth_tools import rfc_1123_date

from vws_mock_contract_tests.utils import Endpoint
from vws_mock_contract_tests.utils.assertions import assert_vws_failure
from vws_mock_contract_tests.utils.too_many_requests import (
    handle_server_errors,
)


def test_missing(endpoint: Endpoint) -> None:
    """
    An `UNAUTHORIZED` response is returned when no `Authorization`
    header
    is given.
    """
    date = rfc_1123_date()
    new_headers: dict[str, str] = {**endpoint.headers, "Date": date}
    _ = new_headers.pop("Authorization", None)
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
        status_code=HTTPStatus.UNAUTHORIZED,
        result_code="AuthenticationFailure",
    )
