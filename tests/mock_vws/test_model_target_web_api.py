"""Verified fake tests for the Model Target Web API."""

import base64
import json
from http import HTTPMethod, HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
import requests

from mock_vws import MockVWS
from tests.mock_vws.fixtures.credentials import (
    ModelTargetCredentials,
    get_model_target_credentials,
)
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend

_VWS_HOST = "https://vws.vuforia.com"
_DATASET_UUID = "0b12466eee5d49409a440927006ff5d8"
_MOCK_BEARER_TOKEN = "mock.header.signature"


def _dataset_request(*, cad_data_url: str) -> dict[str, Any]:
    """Return a standard Model Target dataset request."""
    return {
        "name": f"dataset-{uuid4().hex}",
        "targetSdk": "10.18",
        "models": [
            {
                "name": "model-name",
                "cadDataUrl": cad_data_url,
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


_UNAUTHENTICATED_DATASET_REQUEST = {
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


def _credentials_for_backend(
    *,
    backend: VuforiaBackend,
) -> ModelTargetCredentials:
    """Return credentials for the chosen backend."""
    if backend == VuforiaBackend.REAL:
        return get_model_target_credentials()

    return ModelTargetCredentials(
        client_id="client-id",
        client_secret="client-secret",
        cad_data_url="https://example.com/model.glb",
    )


def _get_access_token(*, credentials: ModelTargetCredentials) -> str:
    """Return an OAuth2 access token."""
    response = requests.post(
        url=f"{_VWS_HOST}/oauth2/token",
        auth=(credentials.client_id, credentials.client_secret),
        data={"grant_type": "client_credentials"},
        timeout=30,
    )

    assert response.status_code == HTTPStatus.OK
    response_json: dict[str, Any] = json.loads(s=response.text)
    access_token = response_json["access_token"]
    assert isinstance(access_token, str)
    assert response_json["token_type"] == "bearer"
    return access_token


def _assert_model_target_error(
    *,
    response: requests.Response,
    status_code: HTTPStatus,
    code: str,
    message: str,
    target: str,
) -> None:
    """Assert a Model Target Web API error response."""
    assert response.status_code == status_code
    assert response.json() == {
        "error": {
            "code": code,
            "message": message,
            "target": target,
        },
    }


def _assert_oauth2_error(
    *,
    response: requests.Response,
    status_code: HTTPStatus,
    body: dict[str, str],
) -> None:
    """Assert an OAuth2 error response."""
    assert response.status_code == status_code
    assert response.json() == body


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
class TestAuthentication:
    """Tests for Model Target Web API authentication."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("method", "path", "json_body"),
        argvalues=[
            pytest.param(
                HTTPMethod.POST,
                "/modeltargets/datasets",
                _UNAUTHENTICATED_DATASET_REQUEST,
                id="create-standard-dataset",
            ),
            pytest.param(
                HTTPMethod.POST,
                "/modeltargets/advancedDatasets",
                _UNAUTHENTICATED_DATASET_REQUEST,
                id="create-advanced-dataset",
            ),
            pytest.param(
                HTTPMethod.GET,
                f"/modeltargets/datasets/{_DATASET_UUID}/status",
                None,
                id="standard-dataset-status",
            ),
            pytest.param(
                HTTPMethod.GET,
                f"/modeltargets/advancedDatasets/{_DATASET_UUID}/status",
                None,
                id="advanced-dataset-status",
            ),
            pytest.param(
                HTTPMethod.GET,
                f"/modeltargets/datasets/{_DATASET_UUID}/dataset",
                None,
                id="download-standard-dataset",
            ),
            pytest.param(
                HTTPMethod.GET,
                f"/modeltargets/advancedDatasets/{_DATASET_UUID}/dataset",
                None,
                id="download-advanced-dataset",
            ),
            pytest.param(
                HTTPMethod.DELETE,
                f"/modeltargets/datasets/{_DATASET_UUID}",
                None,
                id="delete-standard-dataset",
            ),
            pytest.param(
                HTTPMethod.DELETE,
                f"/modeltargets/advancedDatasets/{_DATASET_UUID}",
                None,
                id="delete-advanced-dataset",
            ),
        ],
    )
    def test_missing_bearer_token(
        *,
        method: HTTPMethod,
        path: str,
        json_body: dict[str, object] | None,
    ) -> None:
        """Model Target routes require an OAuth2 bearer token."""
        response = requests.request(
            method=method,
            url=f"{_VWS_HOST}{path}",
            json=json_body,
            timeout=30,
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert response.json() == {
            "error": {
                "code": "401",
                "message": "no Bearer token",
                "target": "jwt",
            },
        }

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("authorization", "message"),
        argvalues=[
            pytest.param("Bearer ", "no Bearer token", id="blank"),
            pytest.param(
                "Bearer invalid-token",
                "Invalid JWT serialization: Missing dot delimiter(s)",
                id="malformed",
            ),
        ],
    )
    def test_invalid_bearer_token(
        *,
        authorization: str,
        message: str,
    ) -> None:
        """Invalid bearer tokens are rejected."""
        response = requests.get(
            url=f"{_VWS_HOST}/modeltargets/datasets/{_DATASET_UUID}/status",
            headers={"Authorization": authorization},
            timeout=30,
        )

        _assert_model_target_error(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message=message,
            target="jwt",
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("auth", "data", "status_code", "body"),
        argvalues=[
            pytest.param(
                None,
                {"grant_type": "client_credentials"},
                HTTPStatus.UNAUTHORIZED,
                {
                    "error": "invalid_request",
                    "error_description": (
                        "Missing or invalid authorization header"
                    ),
                },
                id="missing-basic-auth",
            ),
            pytest.param(
                ("invalid-client-id", "invalid-client-secret"),
                {"grant_type": "client_credentials"},
                HTTPStatus.UNAUTHORIZED,
                {"error": "invalid_client"},
                id="invalid-client",
            ),
            pytest.param(
                ("invalid-client-id", "invalid-client-secret"),
                {"grant_type": "unsupported"},
                HTTPStatus.BAD_REQUEST,
                {"error": "unsupported_grant_type"},
                id="unsupported-grant-type",
            ),
        ],
    )
    def test_invalid_oauth2_token_request(
        *,
        auth: tuple[str, str] | None,
        data: dict[str, str],
        status_code: HTTPStatus,
        body: dict[str, str],
    ) -> None:
        """Invalid OAuth2 token requests are rejected."""
        response = requests.post(
            url=f"{_VWS_HOST}/oauth2/token",
            auth=auth,
            data=data,
            timeout=30,
        )

        _assert_oauth2_error(
            response=response,
            status_code=status_code,
            body=body,
        )


class TestMockErrors:
    """Tests for mock-only Model Target Web API error paths."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames="authorization",
        argvalues=[
            pytest.param("Basic not-base64!", id="invalid-base64"),
            pytest.param(
                (
                    "Basic "
                    + base64.b64encode(s=b"client-id-without-secret").decode()
                ),
                id="missing-separator",
            ),
        ],
    )
    def test_invalid_basic_auth_header(*, authorization: str) -> None:
        """Malformed OAuth2 Basic auth headers are rejected."""
        with MockVWS():
            response = requests.post(
                url=f"{_VWS_HOST}/oauth2/token",
                headers={"Authorization": authorization},
                data={"grant_type": "client_credentials"},
                timeout=30,
            )

        _assert_oauth2_error(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            body={
                "error": "invalid_request",
                "error_description": "Missing or invalid authorization header",
            },
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("body", "headers", "message", "target"),
        argvalues=[
            pytest.param(
                "{}",
                {},
                "Content-Type must be application/json.",
                "Content-Type",
                id="wrong-content-type",
            ),
            pytest.param(
                "{",
                {"Content-Type": "application/json"},
                "Request body must be valid JSON.",
                "body",
                id="invalid-json",
            ),
        ],
    )
    def test_invalid_request_body(
        *,
        body: str,
        headers: dict[str, str],
        message: str,
        target: str,
    ) -> None:
        """Invalid dataset request bodies are rejected."""
        with MockVWS():
            response = requests.post(
                url=f"{_VWS_HOST}/modeltargets/datasets",
                headers={
                    "Authorization": f"Bearer {_MOCK_BEARER_TOKEN}",
                    **headers,
                },
                data=body,
                timeout=30,
            )

        _assert_model_target_error(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            code="BAD_REQUEST",
            message=message,
            target=target,
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("path", "body", "message", "target"),
        argvalues=[
            pytest.param(
                "/modeltargets/datasets",
                {},
                "Missing required field: name.",
                "name",
                id="missing-name",
            ),
            pytest.param(
                "/modeltargets/datasets",
                {
                    "name": "dataset-name",
                    "targetSdk": "10.18",
                    "models": "model",
                },
                "models must be a list.",
                "models",
                id="models-not-list",
            ),
            pytest.param(
                "/modeltargets/datasets",
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [],
                },
                "Standard Model Target datasets must have one model.",
                "models",
                id="standard-model-count",
            ),
            pytest.param(
                "/modeltargets/advancedDatasets",
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        *_UNAUTHENTICATED_DATASET_REQUEST["models"],
                    ]
                    * 21,
                },
                "Advanced Model Target datasets must have 1 to 20 models.",
                "models",
                id="advanced-model-count",
            ),
        ],
    )
    def test_invalid_dataset_request(
        *,
        path: str,
        body: dict[str, object],
        message: str,
        target: str,
    ) -> None:
        """Invalid dataset creation requests are rejected."""
        with MockVWS():
            response = requests.post(
                url=f"{_VWS_HOST}{path}",
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                json=body,
                timeout=30,
            )

        _assert_model_target_error(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            code="BAD_REQUEST",
            message=message,
            target=target,
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("method", "path"),
        argvalues=[
            pytest.param(
                HTTPMethod.GET,
                f"/modeltargets/datasets/{_DATASET_UUID}/status",
                id="status",
            ),
            pytest.param(
                HTTPMethod.GET,
                f"/modeltargets/datasets/{_DATASET_UUID}/dataset",
                id="download",
            ),
            pytest.param(
                HTTPMethod.DELETE,
                f"/modeltargets/datasets/{_DATASET_UUID}",
                id="delete",
            ),
        ],
    )
    def test_unknown_dataset(
        *,
        method: HTTPMethod,
        path: str,
    ) -> None:
        """Unknown datasets are rejected."""
        with MockVWS():
            response = requests.request(
                method=method,
                url=f"{_VWS_HOST}{path}",
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                timeout=30,
            )

        _assert_model_target_error(
            response=response,
            status_code=HTTPStatus.NOT_FOUND,
            code="404",
            message="The dataset was not found.",
            target="uuid",
        )

    @staticmethod
    def test_processing_dataset_cannot_be_downloaded() -> None:
        """A dataset cannot be downloaded while it is still processing."""
        with MockVWS(processing_time_seconds=60):
            create_response = requests.post(
                url=f"{_VWS_HOST}/modeltargets/datasets",
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                json=_UNAUTHENTICATED_DATASET_REQUEST,
                timeout=30,
            )
            response = requests.get(
                url=(
                    f"{_VWS_HOST}/modeltargets/datasets/"
                    f"{create_response.json()['uuid']}/dataset"
                ),
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                timeout=30,
            )

        _assert_model_target_error(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="UNPROCESSABLE_ENTITY",
            message="The dataset is still processing.",
            target="uuid",
        )


class TestStandardDataset:
    """Tests for standard Model Target datasets."""

    @staticmethod
    def test_create_status_and_delete(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """A standard Model Target dataset can be created and deleted."""
        credentials = _credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = _get_access_token(credentials=credentials)
        headers = {"Authorization": f"Bearer {access_token}"}
        dataset_uuid: str | None = None

        try:
            create_response = requests.post(
                url=f"{_VWS_HOST}/modeltargets/datasets",
                headers=headers,
                json=_dataset_request(cad_data_url=credentials.cad_data_url),
                timeout=30,
            )

            assert create_response.status_code == HTTPStatus.CREATED
            create_response_json: dict[str, Any] = json.loads(
                s=create_response.text,
            )
            dataset_uuid_value = create_response_json["uuid"]
            assert isinstance(dataset_uuid_value, str)
            dataset_uuid = dataset_uuid_value

            status_response = requests.get(
                url=(
                    f"{_VWS_HOST}/modeltargets/datasets/{dataset_uuid}/status"
                ),
                headers=headers,
                timeout=30,
            )

            assert status_response.status_code == HTTPStatus.OK
            status_response_json: dict[str, Any] = json.loads(
                s=status_response.text,
            )
            assert status_response_json["status"] in {
                "processing",
                "done",
                "failed",
            }
            assert isinstance(status_response_json["createdAt"], str)
        finally:
            if dataset_uuid is not None:  # pragma: no branch
                delete_response = requests.delete(
                    url=f"{_VWS_HOST}/modeltargets/datasets/{dataset_uuid}",
                    headers=headers,
                    timeout=30,
                )
                assert delete_response.status_code in {
                    HTTPStatus.OK,
                    HTTPStatus.NO_CONTENT,
                }
