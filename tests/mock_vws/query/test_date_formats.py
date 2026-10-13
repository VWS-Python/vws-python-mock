"""Tests for various date formats.

The date format for the VWS API as per
https://library.vuforia.com/articles/Training/Using-the-VWS-API.html must
be in the rfc1123-date format.

However, for the query endpoint, the documentation does not mention the
format. It says:

> The data format must exactly match the Date that is sent in the `Date`
> header.
"""

import datetime
import io
import json
from http import HTTPMethod
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import pytest
import requests
from urllib3.filepost import encode_multipart_formdata
from vws.response import Response
from vws_auth_tools import authorization_header

from mock_vws.database import CloudDatabase
from tests.mock_vws.utils.assertions import (
    assert_query_success,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors


@pytest.mark.parametrize(
    argnames="datetime_format",
    argvalues=[
        "%a, %b %d %H:%M:%S %Y",
        "%a %b %d %H:%M:%S %Y",
        "%a, %d %b %Y %H:%M:%S",
        "%a %d %b %Y %H:%M:%S",
    ],
)
@pytest.mark.parametrize(argnames="include_tz", argvalues=[True, False])
def test_date_formats(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
    datetime_format: str,
    include_tz: bool,
    base_vwq_url: str,
) -> None:
    """Test various date formats which are known to be accepted.

    We expect that more formats than this will be accepted. These
    are the accepted ones we know of at the time of writing.
    """
    image_content = high_quality_image.getvalue()
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}

    if include_tz:
        datetime_format += " GMT"

    gmt = ZoneInfo(key="GMT")
    now = datetime.datetime.now(tz=gmt)
    date = now.strftime(format=datetime_format)
    request_path = "/v1/query"
    content, content_type_header = encode_multipart_formdata(fields=body)
    method = HTTPMethod.POST

    access_key = vuforia_database.client_access_key
    secret_key = vuforia_database.client_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        content_type="multipart/form-data",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
        "Content-Type": content_type_header,
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
    assert_query_success(response=vws_response)
    response_json = json.loads(s=requests_response.text)
    assert response_json["results"] == []
