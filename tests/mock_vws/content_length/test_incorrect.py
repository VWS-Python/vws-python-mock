"""Tests for the ``Content-Length`` header set incorrectly.

We cannot test what happens if ``Content-Length`` is removed from a
prepared request because ``requests-mock`` behaves differently to
``requests`` - https://github.com/jamielennox/requests-mock/issues/80.
"""

import textwrap
from http import HTTPStatus

import pytest

from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_valid_date_header,
    assert_vwq_failure,
    assert_vws_failure,
)
from tests.mock_vws.utils.backend_capabilities import BackendCapabilities
from tests.mock_vws.utils.too_many_requests import handle_server_errors


def test_not_integer(endpoint: Endpoint, base_vwq_url: str) -> None:
    """
    A ``BAD_REQUEST`` error is given when the given ``Content-
    Length`` is
    not an integer.
    """
    if not bool(endpoint.headers.get("Content-Type")):
        return

    content_length = "0.4"

    new_headers = {
        **endpoint.headers,
        "Content-Length": content_length,
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
    assert response.status_code == HTTPStatus.BAD_REQUEST

    if endpoint.base_url == base_vwq_url:
        assert not bool(response.text)
        assert response.headers == {
            "Content-Length": str(object=len(response.text)),
            "Connection": "Close",
        }
        return

    assert_valid_date_header(response=response)
    expected_response_text = textwrap.dedent(
        text="""\
            <html>\r
            <head><title>400 Bad Request</title></head>\r
            <body>\r
            <center><h1>400 Bad Request</h1></center>\r
            </body>\r
            </html>\r
            """,
    )
    assert response.text == expected_response_text
    expected_headers = {
        "Content-Length": str(object=len(response.text)),
        "Content-Type": "text/html",
        "Connection": "close",
        "Server": "awselb/2.0",
        "Date": response.headers["Date"],
    }
    assert response.headers == expected_headers


def test_too_large(
    endpoint: Endpoint,
    backend_capabilities: BackendCapabilities,
    base_vwq_url: str,
) -> None:
    """An error is given if the given content length is too large."""
    if not backend_capabilities.fast_oversized_content_length_response:
        pytest.skip(
            reason="This backend responds slowly to oversized Content-Length."
        )

    if not bool(endpoint.headers.get("Content-Type")):
        pytest.skip(reason="No Content-Type header for this request")

    content_length = str(object=int(endpoint.headers["Content-Length"]) + 1)

    new_headers = {
        **endpoint.headers,
        "Content-Length": content_length,
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

    # We do not use ``handle_server_errors`` here because we do not want to
    # retry on the Gateway Timeout.
    if endpoint.base_url == base_vwq_url:
        assert response.status_code == HTTPStatus.GATEWAY_TIMEOUT
        assert not bool(response.text)
        assert response.headers == {
            "Content-Length": str(object=len(response.text)),
            "Connection": "keep-alive",
        }
        return

    handle_server_errors(response=response)
    assert_valid_date_header(response=response)
    # We have seen both of these response texts.
    assert response.text in {"stream timeout", ""}
    expected_headers = {
        "Content-Length": str(object=len(response.text)),
        "Connection": "close",
        "Content-Type": "text/plain",
        "server": "envoy",
        "Date": response.headers["Date"],
    }
    assert response.headers == expected_headers
    assert response.status_code == HTTPStatus.REQUEST_TIMEOUT


def test_too_small(endpoint: Endpoint, base_vwq_url: str) -> None:
    """
    An ``UNAUTHORIZED`` response is given if the given content
    length is
    too small.
    """
    if not bool(endpoint.headers.get("Content-Type")):
        return

    real_content_length = len(endpoint.data)
    content_length = real_content_length - 1

    new_headers = {
        **endpoint.headers,
        "Content-Length": str(object=content_length),
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
            content_type="application/json",
            cache_control=None,
            www_authenticate="VWS",
            connection="keep-alive",
        )
        return

    assert_vws_failure(
        response=response,
        status_code=HTTPStatus.UNAUTHORIZED,
        result_code="AuthenticationFailure",
    )
