"""Tests for the Content-Type header."""

import io
import json
from http import HTTPMethod, HTTPStatus
from urllib.parse import urljoin

import pytest
import requests
from urllib3.filepost import encode_multipart_formdata
from vws.response import Response
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws.database import CloudDatabase
from tests.mock_vws.query.helpers import (
    JETTY_CONTENT_TYPE_ERROR,
    JETTY_VERSION_RE,
    VWQ_HOST,
)
from tests.mock_vws.utils.assertions import (
    assert_query_success,
    assert_vwq_failure,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors


@pytest.mark.parametrize(
    argnames=(
        "content_type",
        "resp_status_code",
        "resp_content_type",
        "resp_cache_control",
        "resp_text",
    ),
    argvalues=[
        (
            "text/html",
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            None,
            None,
            "",
        ),
        (
            "",
            HTTPStatus.BAD_REQUEST,
            "text/html;charset=iso-8859-1",
            "must-revalidate,no-cache,no-store",
            JETTY_CONTENT_TYPE_ERROR,
        ),
        (
            "*/*",
            HTTPStatus.BAD_REQUEST,
            "text/plain;charset=utf-8",
            None,
            "Unable to get boundary for multipart",
        ),
        (
            "text/*",
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            None,
            None,
            "",
        ),
        (
            "text/plain",
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            None,
            None,
            "",
        ),
    ],
)
def test_incorrect_no_boundary(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
    content_type: str,
    resp_status_code: int,
    resp_content_type: str | None,
    resp_cache_control: str | None,
    resp_text: str,
) -> None:
    """With bad Content-Type headers we get a variety of results."""
    image_content = high_quality_image.getvalue()
    date = rfc_1123_date()
    request_path = "/v1/query"
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}
    content, _ = encode_multipart_formdata(fields=body)
    method = HTTPMethod.POST

    access_key = vuforia_database.client_access_key
    secret_key = vuforia_database.client_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
        "Content-Type": content_type,
    }

    requests_response = requests.request(
        method=method,
        url=urljoin(base=VWQ_HOST, url=request_path),
        headers=headers,
        data=content,
        timeout=30,
    )

    vws_response = Response(
        text=requests_response.text,
        url=requests_response.url,
        status_code=requests_response.status_code,
        headers=dict(requests_response.headers),
        request_body=requests_response.request.body,
        tell_position=requests_response.raw.tell(),
        content=requests_response.content,
    )

    handle_server_errors(response=vws_response)

    repl = "Powered by Jetty://"
    sub = JETTY_VERSION_RE.sub
    actual = sub(repl=repl, string=requests_response.text)
    expected = sub(repl=repl, string=resp_text)
    assert actual == expected
    assert_vwq_failure(
        response=vws_response,
        status_code=resp_status_code,
        content_type=resp_content_type,
        cache_control=resp_cache_control,
        www_authenticate=None,
        connection="keep-alive",
    )


def test_incorrect_with_boundary(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
) -> None:
    """
    If a Content-Type header which is not ``multipart/form-data`` is
    given
    with the correct boundary, an ``UNSUPPORTED_MEDIA_TYPE`` response
    is
    given.
    """
    image_content = high_quality_image.getvalue()
    date = rfc_1123_date()
    request_path = "/v1/query"
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}
    content, content_type_header = encode_multipart_formdata(fields=body)
    method = HTTPMethod.POST

    content_type = "text/html"

    access_key = vuforia_database.client_access_key
    secret_key = vuforia_database.client_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    _, boundary = content_type_header.split(sep=";")

    content_type = "text/html; " + boundary
    headers = {
        "Authorization": authorization_string,
        "Date": date,
        "Content-Type": content_type,
    }

    requests_response = requests.request(
        method=method,
        url=urljoin(base=VWQ_HOST, url=request_path),
        headers=headers,
        data=content,
        timeout=30,
    )

    vws_response = Response(
        text=requests_response.text,
        url=requests_response.url,
        status_code=requests_response.status_code,
        headers=dict(requests_response.headers),
        request_body=requests_response.request.body,
        tell_position=requests_response.raw.tell(),
        content=requests_response.content,
    )
    handle_server_errors(response=vws_response)
    assert not bool(requests_response.text)
    assert_vwq_failure(
        response=vws_response,
        status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        content_type=None,
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )


@pytest.mark.parametrize(
    argnames="content_type",
    argvalues=[
        "multipart/form-data",
        "multipart/form-data; extra",
        "multipart/form-data; extra=1",
    ],
)
def test_no_boundary(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
    content_type: str,
) -> None:
    """If no boundary is given, a ``BAD_REQUEST`` is returned."""
    image_content = high_quality_image.getvalue()
    date = rfc_1123_date()
    request_path = "/v1/query"
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}
    content, _ = encode_multipart_formdata(fields=body)
    method = HTTPMethod.POST

    access_key = vuforia_database.client_access_key
    secret_key = vuforia_database.client_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        # Note that this is not the actual Content-Type header value sent.
        content_type="multipart/form-data",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
        "Content-Type": content_type,
    }

    requests_response = requests.request(
        method=method,
        url=urljoin(base=VWQ_HOST, url=request_path),
        headers=headers,
        data=content,
        timeout=30,
    )

    vws_response = Response(
        text=requests_response.text,
        url=requests_response.url,
        status_code=requests_response.status_code,
        headers=dict(requests_response.headers),
        request_body=requests_response.request.body,
        tell_position=requests_response.raw.tell(),
        content=requests_response.content,
    )
    expected_text = "Unable to get boundary for multipart"
    assert requests_response.text == expected_text
    assert_vwq_failure(
        response=vws_response,
        status_code=HTTPStatus.BAD_REQUEST,
        content_type="text/plain;charset=utf-8",
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )


def test_bogus_boundary(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
) -> None:
    """If a bogus boundary is given, a ``BAD_REQUEST`` is returned."""
    image_content = high_quality_image.getvalue()
    date = rfc_1123_date()
    request_path = "/v1/query"
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}
    content, _ = encode_multipart_formdata(fields=body)
    method = HTTPMethod.POST

    access_key = vuforia_database.client_access_key
    secret_key = vuforia_database.client_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        # Note that this is not the actual Content-Type header value sent.
        content_type="multipart/form-data",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
        "Content-Type": "multipart/form-data; boundary=example_boundary",
    }

    requests_response = requests.request(
        method=method,
        url=urljoin(base=VWQ_HOST, url=request_path),
        headers=headers,
        data=content,
        timeout=30,
    )

    vws_response = Response(
        text=requests_response.text,
        url=requests_response.url,
        status_code=requests_response.status_code,
        headers=dict(requests_response.headers),
        request_body=requests_response.request.body,
        tell_position=requests_response.raw.tell(),
        content=requests_response.content,
    )
    handle_server_errors(response=vws_response)

    expected_text = "No image."
    assert requests_response.text == expected_text
    assert_vwq_failure(
        response=vws_response,
        status_code=HTTPStatus.BAD_REQUEST,
        content_type="application/json",
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )


def test_extra_section(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
) -> None:
    """
    If sections that are not the boundary section are given in the
    header,
    that is fine.
    """
    image_content = high_quality_image.getvalue()
    date = rfc_1123_date()
    request_path = "/v1/query"
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}
    content, content_type_header = encode_multipart_formdata(fields=body)
    method = HTTPMethod.POST

    access_key = vuforia_database.client_access_key
    secret_key = vuforia_database.client_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        # Note that this is not the actual Content-Type header value sent.
        content_type="multipart/form-data",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
        "Content-Type": content_type_header + "; extra=1",
    }

    requests_response = requests.request(
        method=method,
        url=urljoin(base=VWQ_HOST, url=request_path),
        headers=headers,
        data=content,
        timeout=30,
    )

    vws_response = Response(
        text=requests_response.text,
        url=requests_response.url,
        status_code=requests_response.status_code,
        headers=dict(requests_response.headers),
        request_body=requests_response.request.body,
        tell_position=requests_response.raw.tell(),
        content=requests_response.content,
    )
    handle_server_errors(response=vws_response)
    assert_query_success(response=vws_response)
    response_json = json.loads(s=requests_response.text)
    assert response_json["results"] == []
