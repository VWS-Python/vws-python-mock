"""
Tests for the ``Content-Length`` header.
"""
from __future__ import annotations

import textwrap
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
import requests
from mock_vws._constants import ResultCodes
from requests.structures import CaseInsensitiveDict

from tests.mock_vws.utils.assertions import (
    assert_valid_date_header,
    assert_vwq_failure,
    assert_vws_failure,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors

if TYPE_CHECKING:
    from tests.mock_vws.utils import Endpoint


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestIncorrect:
    """
    Tests for the ``Content-Length`` header set incorrectly.

    We cannot test what happens if ``Content-Length`` is removed from a
    prepared request because ``requests-mock`` behaves differently to
    ``requests`` - https://github.com/jamielennox/requests-mock/issues/80.
    """

    @staticmethod
    def test_not_integer(endpoint: Endpoint) -> None:
        """
        A ``BAD_REQUEST`` error is given when the given ``Content-Length`` is
        not an integer.
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        if not endpoint_headers.get("Content-Type"):
            return

        content_length = "0.4"
        headers = endpoint_headers | {"Content-Length": content_length}
        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)
        assert response.status_code == HTTPStatus.BAD_REQUEST

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert not response.text
            assert response.headers == CaseInsensitiveDict(
                data={
                    "Content-Length": str(len(response.text)),
                    "Connection": "Close",
                },
            )
            return

        assert_valid_date_header(response=response)
        expected_response_text = textwrap.dedent(
            """\
            <html>\r
            <head><title>400 Bad Request</title></head>\r
            <body>\r
            <center><h1>400 Bad Request</h1></center>\r
            </body>\r
            </html>\r
            """,
        )
        assert response.text == expected_response_text
        expected_headers = CaseInsensitiveDict(
            data={
                "Content-Length": str(len(response.text)),
                "Content-Type": "text/html",
                "Connection": "close",
                "server": "awselb/2.0",
                "Date": response.headers["Date"],
            },
        )
        assert response.headers == expected_headers

    @staticmethod
    @pytest.mark.skip(reason="It takes too long to run this test.")
    def test_too_large(endpoint: Endpoint) -> None:  # pragma: no cover
        """
        An error is given if the given content length is too large.
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        if not endpoint_headers.get("Content-Type"):
            pytest.skip("No Content-Type header for this request")

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        content_length = str(int(endpoint_headers["Content-Length"]) + 1)
        headers = endpoint_headers | {"Content-Length": content_length}

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        # We do not use ``handle_server_errors`` here because we do not want to
        # retry on the Gateway Timeout.
        if netloc == "cloudreco.vuforia.com":
            assert response.status_code == HTTPStatus.GATEWAY_TIMEOUT
            assert not response.text
            assert response.headers == CaseInsensitiveDict(
                data={
                    "Content-Length": str(len(response.text)),
                    "Connection": "keep-alive",
                },
            )
            return

        handle_server_errors(response=response)
        assert_valid_date_header(response=response)
        # We have seen both of these response texts.
        assert response.text in {"stream timeout", ""}
        expected_headers = {
            "Content-Length": str(len(response.text)),
            "Connection": "close",
            "Content-Type": "text/plain",
            "server": "envoy",
            "Date": response.headers["Date"],
        }
        assert response.headers == CaseInsensitiveDict(
            data=expected_headers,
        )
        assert response.status_code == HTTPStatus.REQUEST_TIMEOUT

    @staticmethod
    def test_too_small(endpoint: Endpoint) -> None:
        """
        An ``UNAUTHORIZED`` response is given if the given content length is
        too small.
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        if not endpoint_headers.get("Content-Type"):
            return

        content_length = str(int(endpoint_headers["Content-Length"]) - 1)
        headers = endpoint_headers | {"Content-Length": content_length}

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
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
