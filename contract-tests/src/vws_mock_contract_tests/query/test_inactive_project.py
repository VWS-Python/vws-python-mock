"""Tests for inactive projects."""

import io
import json
from http import HTTPStatus

import pytest
from vws import CloudRecoService
from vws.exceptions.cloud_reco_exceptions import (
    InactiveProjectError,
)

from vws_mock_contract_tests.utils.assertions import (
    assert_valid_transaction_id,
    assert_vwq_failure,
)


def test_inactive_project(
    *,
    high_quality_image: io.BytesIO,
    inactive_cloud_reco_client: CloudRecoService,
) -> None:
    """
    If the project is inactive, a FORBIDDEN response is
    returned.
    """
    with pytest.raises(expected_exception=InactiveProjectError) as exc_info:
        _ = inactive_cloud_reco_client.query(image=high_quality_image)

    response = exc_info.value.response

    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.FORBIDDEN,
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
        f'"result_code":"InactiveProject"'
        "}"
    )
    assert response.text == expected_text
