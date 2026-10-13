"""Tests for header lines which do not fit in NGINX's 8 KiB buffer.

A header line is the header name, a colon, a space and the value.
NGINX's buffer also holds the line's CRLF, so the longest accepted
line is 8190 bytes.
"""

from urllib.parse import urlparse

from mock_vws._mock_common import MAX_HEADER_LINE_LENGTH
from tests.mock_vws.header_size.helpers import (
    assert_nginx_too_large_response,
    endpoint_with_header,
    header_value_for_line_length,
)
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_query_success,
    assert_valid_date_header,
    assert_vws_response,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors


def test_header_too_large(endpoint: Endpoint) -> None:
    """A header line one byte too long for NGINX gives a
    ``BAD_REQUEST``
    response with NGINX's HTML body, before any authorization.
    """
    name = "X-Padding"
    new_endpoint = endpoint_with_header(
        endpoint=endpoint,
        name=name,
        value=header_value_for_line_length(
            name=name,
            line_length=MAX_HEADER_LINE_LENGTH + 1,
        ),
    )

    response = new_endpoint.send()
    handle_server_errors(response=response)
    assert_valid_date_header(response=response)
    assert_nginx_too_large_response(
        endpoint=endpoint,
        response=response,
    )


def test_cookie_too_large(endpoint: Endpoint) -> None:
    """A cookie which makes the ``Cookie`` line too long for NGINX
    gives
    the same ``BAD_REQUEST`` response as any other header.

    The Envoy layer in front of the Target API lets a ``Cookie`` line
    slightly over the limit through, so this sends one well over it.
    See :ref:`differences-nginx-error-cases`.
    """
    name = "Cookie"
    new_endpoint = endpoint_with_header(
        endpoint=endpoint,
        name=name,
        value="pad="
        + header_value_for_line_length(
            name=name,
            line_length=MAX_HEADER_LINE_LENGTH + 1000,
        ),
    )

    response = new_endpoint.send()
    handle_server_errors(response=response)
    assert_valid_date_header(response=response)
    assert_nginx_too_large_response(
        endpoint=endpoint,
        response=response,
    )


def test_large_header_within_limit(endpoint: Endpoint) -> None:
    """A large header line which fits in NGINX's buffer is accepted.

    This does not send a line at the limit exactly, because the Query
    API rejects header blocks of about 8 KiB in total with a ``431``
    response from its application server. See
    :ref:`differences-nginx-error-cases`.
    """
    name = "X-Padding"
    new_endpoint = endpoint_with_header(
        endpoint=endpoint,
        name=name,
        value=header_value_for_line_length(
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
        assert response.status_code == endpoint.successful_headers_status_code
        return

    assert_vws_response(
        response=response,
        status_code=endpoint.successful_headers_status_code,
        result_code=endpoint.successful_headers_result_code,
    )
