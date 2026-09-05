"""Tests for configurable Cloud Query failure responses."""

import io
from collections.abc import Callable
from http import HTTPMethod, HTTPStatus

import httpx
import httpx2
import pytest
import requests
from urllib3.filepost import encode_multipart_formdata
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws import CloudQueryFailureResponse, MockVWS
from mock_vws.database import CloudDatabase

_QUERY_URL = "https://cloudreco.vuforia.com/v1/query"
type _HTTPResponse = requests.Response | httpx.Response | httpx2.Response
type _QuerySender = Callable[[dict[str, str], bytes], _HTTPResponse]


def _requests_query(headers: dict[str, str], body: bytes) -> _HTTPResponse:
    """Send a Cloud Query request with ``requests``."""
    return requests.post(
        url=_QUERY_URL,
        headers=headers,
        data=body,
        timeout=30,
    )


def _httpx_query(headers: dict[str, str], body: bytes) -> _HTTPResponse:
    """Send a Cloud Query request with ``httpx``."""
    return httpx.post(
        url=_QUERY_URL,
        headers=headers,
        content=body,
        timeout=30,
    )


def _httpx2_query(headers: dict[str, str], body: bytes) -> _HTTPResponse:
    """Send a Cloud Query request with ``httpx2``."""
    return httpx2.post(
        url=_QUERY_URL,
        headers=headers,
        content=body,
        timeout=30,
    )


def _valid_query(
    *,
    database: CloudDatabase,
    image: io.BytesIO,
) -> tuple[dict[str, str], bytes]:
    """Build an otherwise-valid, signed Cloud Query request."""
    request_path = "/v1/query"
    body, content_type = encode_multipart_formdata(
        fields={
            "image": ("image.jpeg", image.getvalue(), "image/jpeg"),
        }
    )
    date = rfc_1123_date()
    authorization = authorization_header(
        access_key=database.client_access_key,
        secret_key=database.client_secret_key,
        method=HTTPMethod.POST,
        content=body,
        content_type="multipart/form-data",
        date=date,
        request_path=request_path,
    )
    headers = {
        "Authorization": authorization,
        "Content-Type": content_type,
        "Date": date,
    }
    return headers, body


@pytest.mark.parametrize(
    argnames="send_query",
    argvalues=[_requests_query, _httpx_query, _httpx2_query],
    ids=["requests", "httpx", "httpx2"],
)
@pytest.mark.parametrize(
    argnames=("status_code", "headers", "body", "expected_body"),
    argvalues=[
        (
            HTTPStatus.BAD_REQUEST,
            {"Content-Length": "0", "X-Query-Failure": "empty"},
            b"",
            b"",
        ),
        (
            HTTPStatus.TOO_MANY_REQUESTS,
            {
                "Content-Type": "text/plain; charset=utf-8",
                "Retry-After": "10",
                "X-Query-Failure": "text",
            },
            "Temporarily unavailable — retry later",
            "Temporarily unavailable — retry later".encode(),
        ),
        (
            HTTPStatus.SERVICE_UNAVAILABLE,
            {"Content-Type": "application/octet-stream"},
            b"\xffupstream failure",
            b"\xffupstream failure",
        ),
    ],
    ids=["empty-4xx", "text-4xx", "raw-5xx"],
)
def test_configured_failure_response(
    *,
    high_quality_image: io.BytesIO,
    send_query: _QuerySender,
    status_code: HTTPStatus,
    headers: dict[str, str],
    body: str | bytes,
    expected_body: bytes,
) -> None:
    """Every in-process backend preserves the configured response."""
    database = CloudDatabase()
    query_headers, query_body = _valid_query(
        database=database,
        image=high_quality_image,
    )
    failure = CloudQueryFailureResponse(
        status_code=status_code,
        headers=headers,
        body=body,
    )

    with MockVWS(cloud_query_failure_response=failure) as mock:
        mock.add_cloud_database(cloud_database=database)
        response = send_query(query_headers, query_body)

    assert response.status_code == status_code
    assert response.content == expected_body
    for name, value in headers.items():
        assert response.headers[name] == value
