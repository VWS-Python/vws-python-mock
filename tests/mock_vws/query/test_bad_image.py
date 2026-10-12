"""Tests for bad images."""

import io
import json
from http import HTTPStatus

import pytest
from vws import CloudRecoService
from vws.exceptions.cloud_reco_exceptions import (
    BadImageError,
)

from tests.mock_vws.utils.assertions import (
    assert_valid_transaction_id,
    assert_vwq_failure,
)


def test_corrupted(
    *,
    corrupted_image_file: io.BytesIO,
    cloud_reco_client: CloudRecoService,
) -> None:
    """A ``BadImage`` response is returned when a corrupted image is
    given.
    """
    with pytest.raises(expected_exception=BadImageError) as exc_info:
        _ = cloud_reco_client.query(image=corrupted_image_file)

    response = exc_info.value.response

    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content_type="application/json",
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )


def test_not_image(cloud_reco_client: CloudRecoService) -> None:
    """
    An ``UNPROCESSABLE_ENTITY`` response is returned when a non-
    image is
    given.
    """
    not_image_data = b"not_image_data"

    with pytest.raises(expected_exception=BadImageError) as exc_info:
        _ = cloud_reco_client.query(
            image=io.BytesIO(initial_bytes=not_image_data)
        )

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
