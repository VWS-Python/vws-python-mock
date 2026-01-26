"""Tests for the ``Content-Length`` header."""

import textwrap
from http import HTTPStatus
from urllib.parse import urlparse

import pytest

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_valid_date_header,
    assert_vwq_failure,
    assert_vws_failure,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestIncorrect:
    """Tests for the ``Content-Length`` header set incorrectly.

    We cannot test what happens if ``Content-Length`` is removed from a
    prepared request because ``requests-mock`` behaves differently to
    ``requests`` - https://github.com/jamielennox/requests-mock/issues/80.
    """

    @staticmethod
    def test_not_integer(endpoint: Endpoint) -> None:
        """
        A ``BAD_REQUEST`` error is given when the given ``Content-
        Length`` is
        not an integer.
        """
        if not endpoint.headers.get("Content-Type"):
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

        netloc = urlparse(url=endpoint.base_url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert not response.text
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

    @staticmethod
    @pytest.mark.skip(reason="It takes too long to run this test.")
    def test_too_large(endpoint: Endpoint) -> None:  # pragma: no cover
        """An error is given if the given content length is too large."""
        if not endpoint.headers.get("Content-Type"):
            pytest.skip(reason="No Content-Type header for this request")

        netloc = urlparse(url=endpoint.base_url).netloc
        content_length = str(
            object=int(endpoint.headers["Content-Length"]) + 1
        )

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
        if netloc == "cloudreco.vuforia.com":
            assert response.status_code == HTTPStatus.GATEWAY_TIMEOUT
            assert not response.text
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

    @staticmethod
    def test_too_small(endpoint: Endpoint) -> None:
        """
        An ``UNAUTHORIZED`` response is given if the given content
        length is
        too small.
        """
        if not endpoint.headers.get("Content-Type"):
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

        netloc = urlparse(url=endpoint.base_url).netloc
        if netloc == "cloudreco.vuforia.com":
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
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )
