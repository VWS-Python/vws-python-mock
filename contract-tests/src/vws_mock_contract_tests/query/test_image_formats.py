"""Tests for various image formats."""

import io
import json
from http import HTTPStatus

import pytest
from PIL import Image
from vws import CloudRecoService
from vws.exceptions.cloud_reco_exceptions import (
    BadImageError,
)

from vws_mock_contract_tests.utils.assertions import (
    assert_valid_transaction_id,
    assert_vwq_failure,
)


@pytest.mark.parametrize(argnames="file_format", argvalues=["png", "jpeg"])
def test_supported(
    *,
    high_quality_image: io.BytesIO,
    file_format: str,
    cloud_reco_client: CloudRecoService,
) -> None:
    """PNG and JPEG formats are supported."""
    image_buffer = io.BytesIO()
    pil_image = Image.open(fp=high_quality_image)
    pil_image.save(fp=image_buffer, format=file_format)
    image_content = image_buffer.getvalue()
    results = cloud_reco_client.query(
        image=io.BytesIO(initial_bytes=image_content)
    )
    assert results == []


def test_unsupported(
    *,
    high_quality_image: io.BytesIO,
    cloud_reco_client: CloudRecoService,
) -> None:
    """File formats which are not PNG or JPEG are not supported."""
    file_format = "tiff"
    image_buffer = io.BytesIO()
    pil_image = Image.open(fp=high_quality_image)
    pil_image.save(fp=image_buffer, format=file_format)
    image_content = image_buffer.getvalue()

    with pytest.raises(expected_exception=BadImageError) as exc_info:
        _ = cloud_reco_client.query(
            image=io.BytesIO(initial_bytes=image_content)
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
