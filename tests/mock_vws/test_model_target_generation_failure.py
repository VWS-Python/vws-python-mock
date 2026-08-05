"""Tests for configurable Model Target dataset generation failures."""

from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import httpx
import pytest
import requests

from mock_vws import MockVWS, ModelTargetGenerationFailure

_AUTHORIZATION = "Bearer eyJhbGciOiJtb2NrIn0.e30.signature"
_CREATE_URL = "https://vws.vuforia.com/modeltargets/datasets"
_REQUEST_BODY: dict[str, Any] = {
    "name": "dataset-name",
    "targetSdk": "10.18",
    "models": [
        {
            "name": "model-name",
            "cadDataUrl": "https://example.com/model.glb",
            "views": [
                {
                    "name": "view-name",
                    "guideViewPosition": {
                        "translation": [0, 0, 5],
                        "rotation": [0, 0, 0, 1],
                    },
                },
            ],
        },
    ],
}
type _HTTPResponse = requests.Response | httpx.Response
type _RequestSender = Callable[[str, dict[str, Any] | None], _HTTPResponse]


def _requests_request(
    url: str,
    json_body: dict[str, Any] | None,
) -> _HTTPResponse:
    """Send a Model Target request with ``requests``."""
    if json_body is None:
        return requests.get(
            url=url,
            headers={"Authorization": _AUTHORIZATION},
            timeout=30,
        )
    return requests.post(
        url=url,
        headers={"Authorization": _AUTHORIZATION},
        json=json_body,
        timeout=30,
    )


def _httpx_request(
    url: str,
    json_body: dict[str, Any] | None,
) -> _HTTPResponse:
    """Send a Model Target request with ``httpx``."""
    if json_body is None:
        return httpx.get(
            url=url,
            headers={"Authorization": _AUTHORIZATION},
            timeout=30,
        )
    return httpx.post(
        url=url,
        headers={"Authorization": _AUTHORIZATION},
        json=json_body,
        timeout=30,
    )


@pytest.mark.parametrize(
    argnames="send_request",
    argvalues=[_requests_request, _httpx_request],
    ids=["requests", "httpx"],
)
@pytest.mark.parametrize(
    argnames=("processing_time_seconds", "expected_status", "time_field"),
    argvalues=[
        pytest.param(60.0, "processing", "eta", id="processing"),
        pytest.param(0.0, "failed", "completedAt", id="failed"),
    ],
)
def test_configured_generation_failure(
    *,
    send_request: _RequestSender,
    processing_time_seconds: float,
    expected_status: str,
    time_field: str,
) -> None:
    """A configured failure is returned only after processing
    completes.
    """
    failure = ModelTargetGenerationFailure(message="CAD model is invalid")
    with MockVWS(
        processing_time_seconds=processing_time_seconds,
        model_target_generation_failure=failure,
    ):
        create_response = send_request(_CREATE_URL, _REQUEST_BODY)
        dataset_uuid = create_response.json()["uuid"]
        status_response = send_request(
            f"{_CREATE_URL}/{dataset_uuid}/status",
            None,
        )

    assert create_response.status_code == HTTPStatus.CREATED
    assert status_response.status_code == HTTPStatus.OK
    status_body = status_response.json()
    assert status_body["status"] == expected_status
    assert status_body["uuid"] == dataset_uuid
    assert isinstance(status_body["createdAt"], str)
    assert isinstance(status_body[time_field], str)
    assert {"eta", "completedAt"} & status_body.keys() == {time_field}
    expected_error = (
        {
            "code": "ERROR",
            "message": "CAD model is invalid",
        }
        if expected_status == "failed"
        else None
    )
    assert status_body.get("error") == expected_error
