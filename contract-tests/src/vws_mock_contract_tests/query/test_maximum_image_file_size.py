"""Tests for maximum image file sizes."""

import io
from http import HTTPStatus

import pytest
from vws import CloudRecoService
from vws.exceptions.custom_exceptions import RequestEntityTooLargeError

from vws_mock_contract_tests.query.helpers import (
    NGINX_REQUEST_ENTITY_TOO_LARGE_ERROR,
)
from vws_mock_contract_tests.utils import (
    make_image_file,
)
from vws_mock_contract_tests.utils.assertions import (
    assert_vwq_failure,
)


def test_png(cloud_reco_client: CloudRecoService) -> None:
    """
    According to
    https://developer.vuforia.com/library/web-api/vuforia-query-web-
    api.
    the maximum file size is "2MiB for PNG".

    Above this limit, a ``REQUEST_ENTITY_TOO_LARGE`` response is returned.
    We do not test exactly at this limit, but that may be beneficial in the
    future.
    """
    max_bytes = 2 * 1024 * 1024
    width = height = 835
    png_not_too_large = make_image_file(
        file_format="PNG",
        color_space="RGB",
        width=width,
        height=height,
    )

    image_content = png_not_too_large.getvalue()

    image_content_size = len(image_content)
    # We check that the image we created is just slightly smaller than the
    # maximum file size.
    #
    # This is just because of the implementation details of
    # ``make_image_file``.
    assert image_content_size < max_bytes
    assert (image_content_size * 1.05) > max_bytes

    results = cloud_reco_client.query(image=png_not_too_large)
    assert results == []

    width += 1
    height += 1
    png_too_large = make_image_file(
        file_format="PNG",
        color_space="RGB",
        width=width,
        height=height,
    )

    image_content = png_too_large.getvalue()
    image_content_size = len(image_content)
    # We check that the image we created is just slightly larger than the
    # maximum file size.
    #
    # This is just because of the implementation details of
    # ``make_image_file``.
    assert image_content_size > max_bytes
    assert (image_content_size * 0.95) < max_bytes

    with pytest.raises(
        expected_exception=RequestEntityTooLargeError
    ) as exc_info:
        _ = cloud_reco_client.query(image=png_too_large)

    response = exc_info.value.response

    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        content_type="text/html",
        cache_control=None,
        www_authenticate=None,
        connection="Close",
    )
    assert response.text == NGINX_REQUEST_ENTITY_TOO_LARGE_ERROR


def test_jpeg(
    cloud_reco_client: CloudRecoService,
    jpeg_too_large: io.BytesIO,
) -> None:
    """
    According to
    https://developer.vuforia.com/library/web-api/vuforia-query-web-
    api.
    the maximum file size is "512 KiB for JPEG".
    However, this test shows that the maximum size for JPEG is 2 MiB.

    Above this limit, a ``REQUEST_ENTITY_TOO_LARGE`` response is returned.
    We do not test exactly at this limit, but that may be beneficial in the
    future.
    """
    max_bytes = 2 * 1024 * 1024
    width = height = 1865
    jpeg_not_too_large = make_image_file(
        file_format="JPEG",
        color_space="RGB",
        width=width,
        height=height,
    )

    image_content = jpeg_not_too_large.getvalue()

    image_content_size = len(image_content)
    # We check that the image we created is just slightly smaller than the
    # maximum file size.
    #
    # This is just because of the implementation details of
    # ``make_image_file``.
    assert image_content_size < max_bytes
    assert (image_content_size * 1.05) > max_bytes

    results = cloud_reco_client.query(image=jpeg_not_too_large)
    assert results == []

    image_content_size = len(jpeg_too_large.getvalue())
    assert image_content_size > max_bytes

    with pytest.raises(
        expected_exception=RequestEntityTooLargeError
    ) as exc_info:
        _ = cloud_reco_client.query(image=jpeg_too_large)

    response = exc_info.value.response

    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        content_type="text/html",
        cache_control=None,
        www_authenticate=None,
        connection="Close",
    )

    assert response.text == NGINX_REQUEST_ENTITY_TOO_LARGE_ERROR
