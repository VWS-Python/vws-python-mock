"""Tests for requests with header lines which are too long."""

from http import HTTPStatus
from urllib.parse import urlparse

import pytest
from vws.response import Response

from mock_vws._mock_common import MAX_HEADER_LINE_LENGTH
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_query_success,
    assert_valid_date_header,
    assert_vws_response,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors

# The body which NGINX gives for a header line which does not fit in its
# 8 KiB header buffer.
_NGINX_TOO_LARGE_RESPONSE_TEXT = "".join(
    f"{line}\r\n"
    for line in (
        "<html>",
        "<head><title>400 Request Header Or Cookie Too Large</title></head>",
        "<body>",
        "<center><h1>400 Bad Request</h1></center>",
        "<center>Request Header Or Cookie Too Large</center>",
        "<hr><center>nginx</center>",
        "</body>",
        "</html>",
    )
)


def _endpoint_with_header(
    *,
    endpoint: Endpoint,
    name: str,
    value: str,
) -> Endpoint:
    """Return the given endpoint with one extra request header."""
    return Endpoint(
        base_url=endpoint.base_url,
        path_url=endpoint.path_url,
        method=endpoint.method,
        headers={**endpoint.headers, name: value},
        data=endpoint.data,
        successful_headers_result_code=endpoint.successful_headers_result_code,
        successful_headers_status_code=endpoint.successful_headers_status_code,
        access_key=endpoint.access_key,
        secret_key=endpoint.secret_key,
    )


def _header_value_for_line_length(*, name: str, line_length: int) -> str:
    """Return a value which makes ``name: value`` the given length."""
    return "a" * (line_length - len(f"{name}: "))


def _assert_nginx_too_large_response(
    *,
    endpoint: Endpoint,
    response: Response,
) -> None:
    """Assert that the response is NGINX's rejection of a long header."""
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.text == _NGINX_TOO_LARGE_RESPONSE_TEXT
    # Header names are compared case-insensitively because the Target API
    # sends some in lower case, and the transports differ in what they keep.
    headers = {key.lower(): value for key, value in response.headers.items()}
    assert headers["content-type"] == "text/html"
    assert headers["content-length"] == str(
        object=len(_NGINX_TOO_LARGE_RESPONSE_TEXT),
    )
    assert headers["connection"] == "keep-alive"

    netloc = urlparse(url=endpoint.base_url).netloc
    if netloc == "cloudreco.vuforia.com":
        assert headers["server"] == "nginx"
        return

    # NGINX for the Target API sits behind Envoy, which adds its own headers.
    assert headers["server"] == "envoy"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["strict-transport-security"] == "max-age=31536000"
    assert "x-aws-region" in headers
    assert "x-envoy-upstream-service-time" in headers


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestOversizedHeaderLine:
    """Tests for header lines which do not fit in NGINX's 8 KiB buffer.

    A header line is the header name, a colon, a space and the value.
    NGINX's buffer also holds the line's CRLF, so the longest accepted
    line is 8190 bytes.
    """

    @staticmethod
    def test_header_too_large(endpoint: Endpoint) -> None:
        """A header line one byte too long for NGINX gives a
        ``BAD_REQUEST``
        response with NGINX's HTML body, before any authorization.
        """
        name = "X-Padding"
        new_endpoint = _endpoint_with_header(
            endpoint=endpoint,
            name=name,
            value=_header_value_for_line_length(
                name=name,
                line_length=MAX_HEADER_LINE_LENGTH + 1,
            ),
        )

        response = new_endpoint.send()
        handle_server_errors(response=response)
        assert_valid_date_header(response=response)
        _assert_nginx_too_large_response(
            endpoint=endpoint,
            response=response,
        )

    @staticmethod
    def test_cookie_too_large(endpoint: Endpoint) -> None:
        """A cookie which makes the ``Cookie`` line too long for NGINX
        gives
        the same ``BAD_REQUEST`` response as any other header.

        The Envoy layer in front of the Target API lets a ``Cookie`` line
        slightly over the limit through, so this sends one well over it.
        See :ref:`differences-nginx-error-cases`.
        """
        name = "Cookie"
        new_endpoint = _endpoint_with_header(
            endpoint=endpoint,
            name=name,
            value="pad="
            + _header_value_for_line_length(
                name=name,
                line_length=MAX_HEADER_LINE_LENGTH + 1000,
            ),
        )

        response = new_endpoint.send()
        handle_server_errors(response=response)
        assert_valid_date_header(response=response)
        _assert_nginx_too_large_response(
            endpoint=endpoint,
            response=response,
        )

    @staticmethod
    def test_large_header_within_limit(endpoint: Endpoint) -> None:
        """A large header line which fits in NGINX's buffer is accepted.

        This does not send a line at the limit exactly, because the Query
        API rejects header blocks of about 8 KiB in total with a ``431``
        response from its application server. See
        :ref:`differences-nginx-error-cases`.
        """
        name = "X-Padding"
        new_endpoint = _endpoint_with_header(
            endpoint=endpoint,
            name=name,
            value=_header_value_for_line_length(
                name=name,
                line_length=MAX_HEADER_LINE_LENGTH // 2,
            ),
        )

        response = new_endpoint.send()
        handle_server_errors(response=response)

        netloc = urlparse(url=endpoint.base_url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert_query_success(response=response)
            return

        if endpoint.successful_headers_result_code is None:
            assert (
                response.status_code == endpoint.successful_headers_status_code
            )
            return

        assert_vws_response(
            response=response,
            status_code=endpoint.successful_headers_status_code,
            result_code=endpoint.successful_headers_result_code,
        )
