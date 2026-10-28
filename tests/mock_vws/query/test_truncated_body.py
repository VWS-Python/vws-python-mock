"""Tests for bodies which end before the multipart body is complete.

A client which is cut off mid-upload sends such a body.
"""

import io
import json
from email.message import EmailMessage
from http import HTTPStatus

from urllib3.filepost import encode_multipart_formdata

from tests.mock_vws.fixtures.credentials import CloudDatabaseCredentials
from tests.mock_vws.query.helpers import (
    query_raw,
)
from tests.mock_vws.utils.assertions import (
    assert_query_success,
    assert_vwq_failure,
)


def test_no_closing_boundary(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabaseCredentials,
    base_vwq_url: str,
) -> None:
    """A body which has all of the image data but no closing boundary
    is
    treated as if the closing boundary were given.
    """
    image_content = high_quality_image.getvalue()
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}
    content, content_type_header = encode_multipart_formdata(fields=body)
    truncated = content[: content.rindex(b"\r\n--")]

    response = query_raw(
        vuforia_database=vuforia_database,
        content=truncated,
        content_type_header=content_type_header,
        base_vwq_url=base_vwq_url,
    )

    assert_query_success(response=response)
    assert json.loads(s=response.text)["results"] == []


def test_partial_closing_boundary(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabaseCredentials,
    base_vwq_url: str,
) -> None:
    """A body which is cut off part-way through its closing boundary is
    treated as if the closing boundary were given.
    """
    image_content = high_quality_image.getvalue()
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}
    content, content_type_header = encode_multipart_formdata(fields=body)
    truncated = content[: content.rindex(b"--")]

    response = query_raw(
        vuforia_database=vuforia_database,
        content=truncated,
        content_type_header=content_type_header,
        base_vwq_url=base_vwq_url,
    )

    assert_query_success(response=response)
    assert json.loads(s=response.text)["results"] == []


def test_truncated_at_end_of_header(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabaseCredentials,
    base_vwq_url: str,
) -> None:
    """A body which is cut off at the end of a header of a part, before
    the line ending of that header, gives a ``BadImage`` response, as
    the
    part has no image data.
    """
    image_content = high_quality_image.getvalue()
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}
    content, content_type_header = encode_multipart_formdata(fields=body)
    first_line_end = content.index(b"\r\n")
    truncated = content[: content.index(b"\r\n", first_line_end + 2)]

    response = query_raw(
        vuforia_database=vuforia_database,
        content=truncated,
        content_type_header=content_type_header,
        base_vwq_url=base_vwq_url,
    )

    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content_type="application/json",
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )
    response_json = json.loads(s=response.text)
    assert response_json["result_code"] == "BadImage"


def test_truncated_image_data(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabaseCredentials,
    base_vwq_url: str,
) -> None:
    """A body which is cut off within the image data gives a
    ``BadImage`` response.
    """
    image_content = high_quality_image.getvalue()
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}
    content, content_type_header = encode_multipart_formdata(fields=body)
    truncated = content[: content.index(b"\r\n\r\n") + 100]

    response = query_raw(
        vuforia_database=vuforia_database,
        content=truncated,
        content_type_header=content_type_header,
        base_vwq_url=base_vwq_url,
    )

    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content_type="application/json",
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )
    response_json = json.loads(s=response.text)
    assert response_json["result_code"] == "BadImage"


def test_truncated_in_part_headers(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabaseCredentials,
    base_vwq_url: str,
) -> None:
    """A body which is cut off within the headers of a part, so that no
    ``Content-Disposition`` header is complete, gives a ``BAD_REQUEST``
    response.
    """
    image_content = high_quality_image.getvalue()
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}
    content, content_type_header = encode_multipart_formdata(fields=body)
    truncated = content[: content.index(b"\r\n") + 20]

    response = query_raw(
        vuforia_database=vuforia_database,
        content=truncated,
        content_type_header=content_type_header,
        base_vwq_url=base_vwq_url,
    )

    expected_text = "Could find no Content-Disposition header within part"
    assert response.text == expected_text
    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        content_type="text/plain;charset=utf-8",
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )


def test_no_content_disposition_header(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabaseCredentials,
    base_vwq_url: str,
) -> None:
    """A complete body with a part which has no ``Content-Disposition``
    header gives a ``BAD_REQUEST`` response.
    """
    image_content = high_quality_image.getvalue()
    body = {"image": ("image.jpeg", image_content, "image/jpeg")}
    _, content_type_header = encode_multipart_formdata(fields=body)
    email_message = EmailMessage()
    email_message["Content-Type"] = content_type_header
    boundary = email_message.get_boundary(failobj="").encode(encoding="utf-8")
    without_content_disposition = (
        b"--"
        + boundary
        + b"\r\nContent-Type: image/jpeg\r\n\r\n"
        + image_content
        + b"\r\n--"
        + boundary
        + b"--\r\n"
    )

    response = query_raw(
        vuforia_database=vuforia_database,
        content=without_content_disposition,
        content_type_header=content_type_header,
        base_vwq_url=base_vwq_url,
    )

    expected_text = "Could find no Content-Disposition header within part"
    assert response.text == expected_text
    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        content_type="text/plain;charset=utf-8",
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )
