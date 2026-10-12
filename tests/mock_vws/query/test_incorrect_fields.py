"""Tests for incorrect and unexpected fields."""

import io
from http import HTTPStatus

from mock_vws.database import CloudDatabase
from tests.mock_vws.query.helpers import (
    query,
)
from tests.mock_vws.utils.assertions import (
    assert_vwq_failure,
)


def test_missing_image(vuforia_database: CloudDatabase) -> None:
    """
    If an image is not given, a ``BAD_REQUEST`` response is
    returned.
    """
    response = query(vuforia_database=vuforia_database, body={})

    assert response.text == "No image."
    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        content_type="application/json",
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )


def test_extra_fields(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
) -> None:
    """If extra fields are given, a ``BAD_REQUEST`` response is
    returned.

    The Query API documentation says that unknown fields are ignored,
    but the real Query API rejects them.
    """
    image_content = high_quality_image.getvalue()
    body = {
        "image": ("image.jpeg", image_content, "image/jpeg"),
        "extra_field": (None, 1, "text/plain"),
    }

    response = query(vuforia_database=vuforia_database, body=body)

    assert response.text == "Unknown parameters in the request."
    assert_vwq_failure(
        response=response,
        content_type="application/json",
        status_code=HTTPStatus.BAD_REQUEST,
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )


def test_missing_image_and_extra_fields(
    vuforia_database: CloudDatabase,
) -> None:
    """If extra fields are given and no image field is given, a
    ``BAD_REQUEST`` response is returned.

    The extra field error takes precedence.
    """
    body = {
        "extra_field": (None, 1, "text/plain"),
    }

    response = query(vuforia_database=vuforia_database, body=body)

    assert response.text == "Unknown parameters in the request."
    assert_vwq_failure(
        response=response,
        content_type="application/json",
        status_code=HTTPStatus.BAD_REQUEST,
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )
