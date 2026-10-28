"""Tests for VuMark generation when the target is still processing.

These use ``mock_only_vuforia`` because there is no way to keep a
VuMark target in PROCESSING state indefinitely on real Vuforia.
"""

import json
from http import HTTPStatus
from uuid import uuid4

import pytest
from vws.exceptions.vws_exceptions import (
    TargetStatusNotSuccessError,
)
from vws.vumark_accept import VuMarkAccept

from vws_mock_contract_tests.fixtures.credentials import (
    VuMarkCloudDatabase,
)
from vws_mock_contract_tests.vumark_generation_api.helpers import (
    make_vumark_request,
    make_vumark_service,
)


def test_processing_target(
    base_vws_url: str,
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> None:
    """A VuMark target still processing returns
    TargetStatusNotSuccess.
    """
    vumark_client = make_vumark_service(
        base_vws_url=base_vws_url,
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key=vumark_vuforia_database.server_secret_key,
    )
    with pytest.raises(
        expected_exception=TargetStatusNotSuccessError,
    ) as exc:
        _ = vumark_client.generate_vumark_instance(
            target_id=vumark_vuforia_database.processing_target_id,
            instance_id=uuid4().hex,
            accept=VuMarkAccept.PNG,
        )

    assert exc.value.response.status_code == HTTPStatus.FORBIDDEN
    response_json = json.loads(s=exc.value.response.text)
    assert response_json["result_code"] == "TargetStatusNotSuccess"


def test_processing_target_raw_response(
    base_vws_url: str,
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> None:
    """The raw HTTP response for a processing target has the expected
    status code and result code.
    """
    response = make_vumark_request(
        base_vws_url=base_vws_url,
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key=vumark_vuforia_database.server_secret_key,
        target_id=vumark_vuforia_database.processing_target_id,
        instance_id=uuid4().hex,
        accept="image/png",
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    response_json = response.json()
    assert response_json["result_code"] == "TargetStatusNotSuccess"
