"""Shared helpers for header size tests."""

from http import HTTPStatus

from vws.response import Response

from vws_mock_contract_tests.utils import Endpoint

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


def endpoint_with_header(
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


def header_value_for_line_length(*, name: str, line_length: int) -> str:
    """Return a value which makes ``name: value`` the given length."""
    return "a" * (line_length - len(f"{name}: "))


def assert_nginx_too_large_response(
    *,
    endpoint: Endpoint,
    response: Response,
    base_vwq_url: str,
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

    if endpoint.base_url == base_vwq_url:
        assert headers["server"] == "nginx"
        return

    # NGINX for the Target API sits behind Envoy, which adds its own headers.
    assert headers["server"] == "envoy"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["strict-transport-security"] == "max-age=31536000"
    assert "x-aws-region" in headers
    assert "x-envoy-upstream-service-time" in headers
