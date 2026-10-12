"""Tests for maximum image dimensions."""

import json
from http import HTTPStatus

import pytest
from vws import CloudRecoService
from vws.exceptions.cloud_reco_exceptions import (
    BadImageError,
)

from tests.mock_vws.utils import (
    make_decompression_bomb_image_file,
    make_image_file,
)
from tests.mock_vws.utils.assertions import (
    assert_valid_transaction_id,
    assert_vwq_failure,
)


def test_max_height(
    cloud_reco_client: CloudRecoService,
) -> None:
    """
    An error is returned when an image with a height greater than
    30000 is
    given.
    """
    width = 1
    max_height = 30000
    png_not_too_tall = make_image_file(
        file_format="PNG",
        color_space="RGB",
        width=width,
        height=max_height,
    )

    results = cloud_reco_client.query(image=png_not_too_tall)
    assert results == []

    png_too_tall = make_image_file(
        file_format="PNG",
        color_space="RGB",
        width=width,
        height=max_height + 1,
    )

    with pytest.raises(expected_exception=BadImageError) as exc_info:
        _ = cloud_reco_client.query(image=png_too_tall)

    response = exc_info.value.response

    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content_type="application/json",
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )

    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert response_json.keys() == {"transaction_id", "result_code"}
    assert_valid_transaction_id(response=response)
    # The separators are inconsistent and we test this.
    expected_text = (
        '{"transaction_id": '
        f'"{response_json["transaction_id"]}",'
        f'"result_code":"BadImage"'
        "}"
    )
    assert response.text == expected_text


def test_max_width(cloud_reco_client: CloudRecoService) -> None:
    """
    An error is returned when an image with a width greater than
    30000 is
    given.
    """
    height = 1
    max_width = 30000
    png_not_too_wide = make_image_file(
        file_format="PNG",
        color_space="RGB",
        width=max_width,
        height=height,
    )

    result = cloud_reco_client.query(image=png_not_too_wide)
    assert result == []

    png_too_wide = make_image_file(
        file_format="PNG",
        color_space="RGB",
        width=max_width + 1,
        height=height,
    )

    with pytest.raises(expected_exception=BadImageError) as exc_info:
        result = cloud_reco_client.query(image=png_too_wide)

    response = exc_info.value.response

    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content_type="application/json",
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )

    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert response_json.keys() == {"transaction_id", "result_code"}
    assert_valid_transaction_id(response=response)
    # The separators are inconsistent and we test this.
    expected_text = (
        '{"transaction_id": '
        f'"{response_json["transaction_id"]}",'
        f'"result_code":"BadImage"'
        "}"
    )
    assert response.text == expected_text


def test_max_pixels(cloud_reco_client: CloudRecoService) -> None:
    """No error is returned for an 835 x 835 image."""
    # If we make this 836 then we hit REQUEST_ENTITY_TOO_LARGE errors.
    max_height = max_width = 835
    png_not_too_wide = make_image_file(
        file_format="PNG",
        color_space="RGB",
        width=max_width,
        height=max_height,
    )

    result = cloud_reco_client.query(image=png_not_too_wide)
    assert result == []


def test_small_file_many_pixels(
    cloud_reco_client: CloudRecoService,
) -> None:
    """
    No error is returned for an image with a small file size and a
    huge number of pixels.

    Unlike ``POST /targets``, the Query API has no limit on the
    number of pixels, only on the width and the height.
    """
    max_bytes = 2 * 1024 * 1024
    image_file = make_decompression_bomb_image_file()
    assert len(image_file.getvalue()) < max_bytes

    result = cloud_reco_client.query(image=image_file)
    assert result == []
