"""Tests for what happens when the `Date` header is missing."""

from http import HTTPStatus

from vws_auth_tools import authorization_header

from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_vwq_failure,
    assert_vws_failure,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors


def test_no_date_header(endpoint: Endpoint, base_vwq_url: str) -> None:
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

    if endpoint.base_url == base_vwq_url:
        expected_content_type = "text/plain;charset=iso-8859-1"
        assert response.text == "Date header required."
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            content_type=expected_content_type,
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )
        return

    assert_vws_failure(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code="Fail",
    )
