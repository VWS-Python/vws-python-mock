"""Tests for passing a malformed ``Authorization`` header."""

from http import HTTPStatus

from vws_auth_tools import rfc_1123_date

from vws_mock_contract_tests.utils import Endpoint
from vws_mock_contract_tests.utils.assertions import assert_vws_failure
from vws_mock_contract_tests.utils.too_many_requests import (
    handle_server_errors,
)


def test_one_part_no_space(endpoint: Endpoint) -> None:
    """A valid authorization string is two "parts" when split on a
    space.

    When
    a string is given which is one "part", a ``BAD_REQUEST`` or
    ``UNAUTHORIZED`` response is returned.
    """
    date = rfc_1123_date()
    authorization_string = "VWS"
    new_headers = {
        **endpoint.headers,
        "Authorization": authorization_string,
        "Date": date,
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


def test_one_part_with_space(endpoint: Endpoint) -> None:
    """A valid authorization string is two "parts" when split on a
    space.

    When
    a string is given which is one "part", a ``BAD_REQUEST`` or
    ``UNAUTHORIZED`` response is returned.
    """
    authorization_string = "VWS "
    date = rfc_1123_date()
    new_headers = {
        **endpoint.headers,
        "Authorization": authorization_string,
        "Date": date,
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


def test_missing_signature(endpoint: Endpoint) -> None:
    """
    If a signature is missing `Authorization` header is given, a
    ``BAD_REQUEST`` response is given.
    """
    date = rfc_1123_date()
    authorization_string = "VWS foobar:"
    new_headers = {
        **endpoint.headers,
        "Authorization": authorization_string,
        "Date": date,
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
