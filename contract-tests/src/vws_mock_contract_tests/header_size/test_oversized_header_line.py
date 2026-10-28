"""Tests for header lines which do not fit in NGINX's 8 KiB buffer.

A header line is the header name, a colon, a space and the value.
NGINX's buffer also holds the line's CRLF, so the longest accepted
line is 8190 bytes.
"""

from vws_mock_contract_tests.header_size.helpers import (
    assert_nginx_too_large_response,
    endpoint_with_header,
    header_value_for_line_length,
)
from vws_mock_contract_tests.utils import Endpoint
from vws_mock_contract_tests.utils.assertions import (
    assert_query_success,
    assert_valid_date_header,
    assert_vws_response,
)
from vws_mock_contract_tests.utils.too_many_requests import (
    handle_server_errors,
)

# The observed NGINX boundary is an API expectation, independent of core.
_MAX_HEADER_LINE_LENGTH = 8190


def test_header_too_large(endpoint: Endpoint, base_vwq_url: str) -> None:
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
            line_length=_MAX_HEADER_LINE_LENGTH + 1,
        ),
    )

    response = new_endpoint.send()
    handle_server_errors(response=response)
    assert_valid_date_header(response=response)
    assert_nginx_too_large_response(
        endpoint=endpoint,
        response=response,
        base_vwq_url=base_vwq_url,
    )


def test_cookie_too_large(endpoint: Endpoint, base_vwq_url: str) -> None:
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
            line_length=_MAX_HEADER_LINE_LENGTH + 1000,
        ),
    )

    response = new_endpoint.send()
    handle_server_errors(response=response)
    assert_valid_date_header(response=response)
    assert_nginx_too_large_response(
        endpoint=endpoint,
        response=response,
        base_vwq_url=base_vwq_url,
    )


def test_large_header_within_limit(
    endpoint: Endpoint, base_vwq_url: str
) -> None:
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
            line_length=_MAX_HEADER_LINE_LENGTH // 2,
        ),
    )

    response = new_endpoint.send()
    handle_server_errors(response=response)

    if endpoint.base_url == base_vwq_url:
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
