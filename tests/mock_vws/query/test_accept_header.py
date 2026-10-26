"""Tests for the ``Accept`` header."""

import io
import json
from http import HTTPMethod, HTTPStatus
from urllib.parse import urljoin

import pytest
import requests
from urllib3.filepost import encode_multipart_formdata
from vws.response import Response
from vws_auth_tools import authorization_header, rfc_1123_date

from tests.mock_vws.fixtures.credentials import CloudDatabaseCredentials
from tests.mock_vws.utils.assertions import (
    assert_query_success,
    assert_vwq_failure,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors


@pytest.mark.parametrize(
    argnames="extra_headers",
    argvalues=[
        {
            "Accept": "application/json",
        },
        {},
    ],
)
def test_valid(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabaseCredentials,
    extra_headers: dict[str, str],
    base_vwq_url: str,
) -> None:
    """An ``Accept`` header can be given iff its value is
    "application/json".
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
        "Content-Type": content_type_header,
    } | extra_headers

    requests_response = requests.request(
        method=method,
        url=urljoin(base=base_vwq_url, url=request_path),
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


def test_invalid(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabaseCredentials,
    base_vwq_url: str,
) -> None:
    """
    A NOT_ACCEPTABLE response is returned if an ``Accept`` header is
    given
    with a value which is not "application/json".
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
        "Content-Type": content_type_header,
        "Accept": "text/html",
    }

    requests_response = requests.request(
        method=method,
        url=urljoin(base=base_vwq_url, url=request_path),
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

    assert_vwq_failure(
        response=vws_response,
        status_code=HTTPStatus.NOT_ACCEPTABLE,
        content_type=None,
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )
