"""Tests for passing a malformed ``Authorization`` header."""

from http import HTTPStatus

from vws_auth_tools import rfc_1123_date

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_vwq_failure,
    assert_vws_failure,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors


def test_one_part_no_space(endpoint: Endpoint, base_vwq_url: str) -> None:
    """A valid authorization string is two "parts" when split on a
    space.

    When
    a string is given which is one "part", a ``BAD_REQUEST`` or
    ``UNAUTHORIZED`` response is returned.
    """
    date = rfc_1123_date()

    # We use "VWS" as this is the first part of a valid authorization
    # string, but really any string which is not two parts when split on a
    # space will do.
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

    if endpoint.base_url == base_vwq_url:
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            content_type="text/plain;charset=iso-8859-1",
            cache_control=None,
            www_authenticate="KWS",
            connection="keep-alive",
        )
        assert response.text == "Malformed authorization header."
        return

    assert_vws_failure(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code=ResultCodes.FAIL,
    )


def test_one_part_with_space(endpoint: Endpoint, base_vwq_url: str) -> None:
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

    if endpoint.base_url == base_vwq_url:
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            content_type="text/plain;charset=iso-8859-1",
            cache_control=None,
            www_authenticate="KWS",
            connection="keep-alive",
        )
        assert response.text == "Malformed authorization header."
        return

    assert_vws_failure(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code=ResultCodes.FAIL,
    )


def test_missing_signature(endpoint: Endpoint, base_vwq_url: str) -> None:
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

    if endpoint.base_url == base_vwq_url:
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            content_type="text/plain;charset=iso-8859-1",
            cache_control=None,
            www_authenticate="KWS",
            connection="keep-alive",
        )
        assert response.text == "Malformed authorization header."
        return

    assert_vws_failure(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code=ResultCodes.FAIL,
    )
