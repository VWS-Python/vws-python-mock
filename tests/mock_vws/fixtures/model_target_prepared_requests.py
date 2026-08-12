"""Fixtures which prepare Model Target Web API requests."""

import json
from http import HTTPMethod, HTTPStatus
from typing import Any

import pytest
import requests
from beartype import beartype

from tests.mock_vws.fixtures.credentials import (
    ModelTargetCredentials,
    get_model_target_credentials,
)
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.utils import ModelTargetEndpoint

MODEL_TARGET_VWS_HOST = "https://vws.vuforia.com"
MODEL_TARGET_DATASET_UUID = "0b12466eee5d49409a440927006ff5d8"

_DATASET_REQUEST: dict[str, Any] = {
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


@beartype
def credentials_for_backend(
    *,
    backend: VuforiaBackend,
) -> ModelTargetCredentials:
    """Return Model Target credentials for the chosen backend."""
    if backend == VuforiaBackend.REAL:
        return get_model_target_credentials()

    return ModelTargetCredentials(
        client_id="client-id",
        client_secret="client-secret",
        cad_data_url="https://example.com/model.glb",
    )


@beartype
def get_access_token(
    *,
    credentials: ModelTargetCredentials,
    backend: VuforiaBackend,
) -> str:
    """Return an OAuth2 access token."""
    response = requests.post(
        url=f"{MODEL_TARGET_VWS_HOST}/oauth2/token",
        auth=(credentials.client_id, credentials.client_secret),
        data={"grant_type": "client_credentials"},
        timeout=30,
    )

    if (
        backend == VuforiaBackend.REAL
        and response.status_code == HTTPStatus.UNAUTHORIZED
        and response.json() == {"error": "invalid_client"}
    ):
        pytest.xfail(
            reason=(
                "Real Model Target Web API credentials are not accepted; "
                "authenticated behavior is verified against the mock "
                "backends only until the credentials are rotated."
            ),
        )

    assert response.status_code == HTTPStatus.OK
    response_json: dict[str, Any] = json.loads(s=response.text)
    access_token = response_json["access_token"]
    assert isinstance(access_token, str)
    assert response_json["token_type"] == "bearer"
    return access_token


@beartype
def _create_dataset_endpoint(*, request_path: str) -> ModelTargetEndpoint:
    """Return details of a dataset creation endpoint."""
    content = json.dumps(obj=_DATASET_REQUEST).encode(encoding="utf-8")
    headers = {
        "Content-Length": str(object=len(content)),
        "Content-Type": "application/json",
    }
    return ModelTargetEndpoint(
        base_url=MODEL_TARGET_VWS_HOST,
        path_url=request_path,
        method=HTTPMethod.POST,
        headers=headers,
        data=content,
        takes_json_body=True,
    )


@beartype
def _get_endpoint(*, request_path: str) -> ModelTargetEndpoint:
    """Return details of a body-less ``GET`` endpoint."""
    return ModelTargetEndpoint(
        base_url=MODEL_TARGET_VWS_HOST,
        path_url=request_path,
        method=HTTPMethod.GET,
        headers={},
        data=b"",
        takes_json_body=False,
    )


@beartype
def _delete_endpoint(*, request_path: str) -> ModelTargetEndpoint:
    """Return details of a body-less ``DELETE`` endpoint."""
    return ModelTargetEndpoint(
        base_url=MODEL_TARGET_VWS_HOST,
        path_url=request_path,
        method=HTTPMethod.DELETE,
        headers={"Content-Length": "0"},
        data=b"",
        takes_json_body=False,
    )


@pytest.fixture
def create_standard_dataset() -> ModelTargetEndpoint:
    """Return details of the endpoint for creating a standard dataset."""
    return _create_dataset_endpoint(request_path="/modeltargets/datasets")


@pytest.fixture
def create_advanced_dataset() -> ModelTargetEndpoint:
    """Return details of the endpoint for creating an advanced dataset."""
    return _create_dataset_endpoint(
        request_path="/modeltargets/advancedDatasets",
    )


@pytest.fixture
def standard_dataset_status() -> ModelTargetEndpoint:
    """Return details of the standard dataset status endpoint."""
    return _get_endpoint(
        request_path=(
            f"/modeltargets/datasets/{MODEL_TARGET_DATASET_UUID}/status"
        ),
    )


@pytest.fixture
def advanced_dataset_status() -> ModelTargetEndpoint:
    """Return details of the advanced dataset status endpoint."""
    return _get_endpoint(
        request_path=(
            f"/modeltargets/advancedDatasets/{MODEL_TARGET_DATASET_UUID}"
            "/status"
        ),
    )


@pytest.fixture
def download_standard_dataset() -> ModelTargetEndpoint:
    """Return details of the standard dataset download endpoint."""
    return _get_endpoint(
        request_path=(
            f"/modeltargets/datasets/{MODEL_TARGET_DATASET_UUID}/dataset"
        ),
    )


@pytest.fixture
def download_advanced_dataset() -> ModelTargetEndpoint:
    """Return details of the advanced dataset download endpoint."""
    return _get_endpoint(
        request_path=(
            f"/modeltargets/advancedDatasets/{MODEL_TARGET_DATASET_UUID}"
            "/dataset"
        ),
    )


@pytest.fixture
def delete_standard_dataset() -> ModelTargetEndpoint:
    """Return details of the standard dataset deletion endpoint."""
    return _delete_endpoint(
        request_path=f"/modeltargets/datasets/{MODEL_TARGET_DATASET_UUID}",
    )


@pytest.fixture
def delete_advanced_dataset() -> ModelTargetEndpoint:
    """Return details of the advanced dataset deletion endpoint."""
    return _delete_endpoint(
        request_path=(
            f"/modeltargets/advancedDatasets/{MODEL_TARGET_DATASET_UUID}"
        ),
    )
