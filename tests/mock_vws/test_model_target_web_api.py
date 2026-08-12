"""Verified fake tests for the Model Target Web API."""

import base64
import io
import json
import zipfile
from http import HTTPMethod, HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
import requests

from mock_vws import MockVWS
from mock_vws.model_target import ModelTargetDataset, ModelTargetDatasetType
from tests.mock_vws.fixtures.credentials import (
    ModelTargetCredentials,
    get_model_target_credentials,
)
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend

_VWS_HOST = "https://vws.vuforia.com"
_DATASET_UUID = "0b12466eee5d49409a440927006ff5d8"
_MOCK_BEARER_TOKEN = "eyJhbGciOiJtb2NrIn0.e30.c2lnbmF0dXJl"


_VIEW: dict[str, Any] = {
    "name": "view-name",
    "guideViewPosition": {
        "translation": [0, 0, 5],
        "rotation": [0, 0, 0, 1],
    },
}


def _dataset_request(*, cad_data_url: str) -> dict[str, Any]:
    """Return a standard Model Target dataset request."""
    return {
        "name": f"dataset-{uuid4().hex}",
        "targetSdk": "10.18",
        "models": [
            {
                "name": "model-name",
                "cadDataUrl": cad_data_url,
                "views": [_VIEW],
            },
        ],
    }


def _cad_data_blob() -> str:
    """Return a base64-encoded zipped model for inline CAD data."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(file=zip_buffer, mode="w") as zip_file:
        zip_file.writestr(
            zinfo_or_arcname="model.gltf",
            data=json.dumps(obj={"asset": {"version": "2.0"}}),
        )
    return base64.b64encode(s=zip_buffer.getvalue()).decode(encoding="ascii")


def _blob_dataset_request() -> dict[str, Any]:
    """Return a standard dataset request with inline CAD data."""
    return {
        "name": f"dataset-{uuid4().hex}",
        "targetSdk": "10.18",
        "models": [
            {
                "name": "model-name",
                "cadDataBlob": _cad_data_blob(),
                "cadDataFormat": "ZIP",
                "views": [_VIEW],
            },
        ],
    }


_MODEL: dict[str, Any] = {
    "name": "model-name",
    "cadDataUrl": "https://example.com/model.glb",
    "views": [_VIEW],
}

_MODEL_WITHOUT_CAD_DATA: dict[str, Any] = {
    key: value for key, value in _MODEL.items() if key != "cadDataUrl"
}

_EMPTY_MODEL: dict[str, Any] = {}

_EMPTY_VIEW: dict[str, Any] = {}

_EMPTY_GUIDE_VIEW_POSITION: list[Any] = []

_EMPTY_GUIDE_VIEW_POSITION_OBJECT: dict[str, Any] = {}

_UNAUTHENTICATED_DATASET_REQUEST: dict[str, Any] = {
    "name": "dataset-name",
    "targetSdk": "10.18",
    "models": [_MODEL],
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


def _get_access_token(
    *,
    credentials: ModelTargetCredentials,
    backend: VuforiaBackend,
) -> str:
    """Return an OAuth2 access token."""
    response = requests.post(
        url=f"{_VWS_HOST}/oauth2/token",
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


def _assert_model_target_error(
    *,
    response: requests.Response,
    status_code: HTTPStatus,
    code: str,
    message: str,
    target: str,
) -> None:
    """Assert a Model Target Web API error response with the legacy
    shape.
    """
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
            pytest.param(
                "Bearer ..",
                "Invalid unsecured/JWS/JWE header: Invalid JSON object",
                id="invalid-header-json",
            ),
            pytest.param(
                "Bearer e30.e30.signature",
                'Missing "alg" in header JSON object',
                id="missing-algorithm",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJub25lIn0.e30.",
                (
                    "Unsecured (plain) JWTs are rejected, extend class to "
                    "handle"
                ),
                id="unsecured",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJSUzI1NiJ9.%.signature",
                "Payload of JWS object is not a valid JSON object",
                id="payload-not-base64",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJSUzI1NiJ9..signature",
                "Payload of JWS object is not a valid JSON object",
                id="blank-payload",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJSUzI1NiJ9.InZhbHVlIg.signature",
                "Payload of JWS object is not a valid JSON object",
                id="payload-not-json-object",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJSUzI1NiJ9.e30.",
                "The signature must not be empty",
                id="blank-signature",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJSUzI1NiJ9.e30.%",
                "Signed JWT rejected: Invalid signature",
                id="signature-not-base64",
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


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
class TestErrorResponses:
    """Verified fake tests for Model Target Web API error responses."""

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
    def test_wrong_content_type(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """Non-JSON dataset bodies are rejected with 415."""
        credentials = _credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = _get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.post(
            url=f"{_VWS_HOST}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {access_token}"},
            data="{}",
            timeout=30,
        )

        assert response.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
        error = response.json()["error"]
        assert error["code"] == "ERROR"
        assert error["message"] == (
            "Expecting text/json or application/json body"
        )
        assert "target" not in error

    @staticmethod
    def test_invalid_json(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """Malformed JSON bodies are rejected with 400."""
        credentials = _credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = _get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.post(
            url=f"{_VWS_HOST}/modeltargets/datasets",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            data="{",
            timeout=30,
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "ERROR"
        assert error["message"].startswith("Invalid Json")
        assert "target" not in error

    @staticmethod
    @pytest.mark.parametrize(
        argnames="body",
        argvalues=[
            pytest.param("[]", id="array"),
            pytest.param('"dataset"', id="string"),
            pytest.param("1", id="number"),
            pytest.param("true", id="boolean"),
            pytest.param("null", id="null"),
        ],
    )
    def test_body_not_json_object(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        body: str,
    ) -> None:
        """JSON bodies which are not objects are missing every field."""
        credentials = _credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = _get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.post(
            url=f"{_VWS_HOST}/modeltargets/datasets",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            data=body,
            timeout=30,
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "BAD_REQUEST"
        assert error["message"] == (
            f"Validation error for request {error['target']}"
        )
        actual_messages = {detail["message"] for detail in error["details"]}
        assert actual_messages == {
            "/models: element is required",
            "/name: element is required",
            "/targetSdk: element is required",
        }
        for detail in error["details"]:
            assert detail["code"] == "VALIDATION_ERROR"

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("body", "expected_messages"),
        argvalues=[
            pytest.param(
                {},
                {
                    "/models: element is required",
                    "/name: element is required",
                    "/targetSdk: element is required",
                },
                id="empty-body",
            ),
            pytest.param(
                {
                    "name": "dataset-name",
                    "targetSdk": "10.18",
                    "models": "model",
                },
                {"/models: error.expected.jsarray"},
                id="models-not-list",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [],
                },
                {"exactly one model should be provided"},
                id="standard-zero-models",
            ),
            pytest.param(
                {**_UNAUTHENTICATED_DATASET_REQUEST, "name": 1},
                {"/name: error.expected.jsstring"},
                id="name-not-string",
            ),
            pytest.param(
                {**_UNAUTHENTICATED_DATASET_REQUEST, "targetSdk": ["10.18"]},
                {"/targetSdk: error.expected.jsstring"},
                id="target-sdk-not-string",
            ),
            pytest.param(
                {"name": None, "targetSdk": None, "models": "model"},
                {
                    "/models: error.expected.jsarray",
                    "/name: error.expected.jsstring",
                    "/targetSdk: error.expected.jsstring",
                },
                id="multiple-type-errors",
            ),
            pytest.param(
                {**_UNAUTHENTICATED_DATASET_REQUEST, "models": ["model"]},
                {"/models(0): error.expected.jsobject"},
                id="model-not-object",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        *_UNAUTHENTICATED_DATASET_REQUEST["models"],
                        "model",
                    ],
                },
                {"/models(1): error.expected.jsobject"},
                id="second-model-not-object",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [_EMPTY_MODEL],
                },
                {
                    (
                        "/models(0): one and only one of cadDataUrl and "
                        "cadDataBlob is required"
                    ),
                    "/models(0)/name: element is required",
                },
                id="model-missing-fields",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [_MODEL_WITHOUT_CAD_DATA],
                },
                {
                    (
                        "/models(0): one and only one of cadDataUrl and "
                        "cadDataBlob is required"
                    ),
                },
                id="model-without-cad-data",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "cadDataBlob": "ZmFrZQ==",
                            "cadDataFormat": "ZIP",
                        },
                    ],
                },
                {
                    (
                        "/models(0): one and only one of cadDataUrl and "
                        "cadDataBlob is required"
                    ),
                },
                id="model-with-both-cad-data-sources",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "cadDataUrl": 1,
                        },
                    ],
                },
                {"/models(0)/cadDataUrl: error.expected.jsstring"},
                id="model-cad-data-url-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL_WITHOUT_CAD_DATA,
                            "cadDataBlob": 1,
                            "cadDataFormat": "ZIP",
                        },
                    ],
                },
                {"/models(0)/cadDataBlob: error.expected.jsstring"},
                id="model-cad-data-blob-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "cadDataFormat": 1}],
                },
                {"/models(0)/cadDataFormat: error.expected.jsstring"},
                id="model-cad-data-format-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "cadDataFormat": "gltf"}],
                },
                {"/models(0)/cadDataFormat: error.expected.validenum"},
                id="model-cad-data-format-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "name": None}],
                },
                {"/models(0)/name: error.expected.jsstring"},
                id="model-name-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "views": "view-name"}],
                },
                {"/models(0)/views: error.expected.jsarray"},
                id="model-views-not-array",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "views": ["view-name"]}],
                },
                {"/models(0)/views(0): error.expected.jsobject"},
                id="view-not-object",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "views": [_EMPTY_VIEW]}],
                },
                {
                    (
                        "/models(0)/views(0)/guideViewPosition: "
                        "element is required"
                    ),
                    "/models(0)/views(0)/name: element is required",
                },
                id="view-missing-fields",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {**_MODEL, "views": [{**_VIEW, "name": 1}]},
                    ],
                },
                {"/models(0)/views(0)/name: error.expected.jsstring"},
                id="view-name-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                _VIEW,
                                {
                                    **_VIEW,
                                    "guideViewPosition": (
                                        _EMPTY_GUIDE_VIEW_POSITION
                                    ),
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(1)/guideViewPosition: "
                        "error.expected.jsobject"
                    ),
                },
                id="view-guide-view-position-not-object",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                {
                                    **_VIEW,
                                    "guideViewPosition": (
                                        _EMPTY_GUIDE_VIEW_POSITION_OBJECT
                                    ),
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(0)/guideViewPosition/rotation: "
                        "element is required"
                    ),
                    (
                        "/models(0)/views(0)/guideViewPosition/translation: "
                        "element is required"
                    ),
                },
                id="guide-view-position-missing-fields",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                {
                                    **_VIEW,
                                    "guideViewPosition": {
                                        "rotation": "0,0,0,1",
                                        "translation": [0, 0, 5],
                                    },
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(0)/guideViewPosition/rotation: "
                        "error.expected.jsarray"
                    ),
                },
                id="guide-view-position-rotation-not-array",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                {
                                    **_VIEW,
                                    "guideViewPosition": {
                                        "rotation": [0, 0, 0, 1],
                                        "translation": 5,
                                    },
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(0)/guideViewPosition/translation: "
                        "error.expected.jsarray"
                    ),
                },
                id="guide-view-position-translation-not-array",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                {
                                    **_VIEW,
                                    "guideViewPosition": {
                                        "rotation": [0, "0", 0, 1],
                                        "translation": [0, 0, 5],
                                    },
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(0)/guideViewPosition/rotation(1): "
                        "error.expected.jsnumber"
                    ),
                },
                id="guide-view-position-rotation-element-not-number",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                {
                                    **_VIEW,
                                    "guideViewPosition": {
                                        "rotation": [0, 0, 0, 1],
                                        "translation": [0, 0, True],
                                    },
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(0)/guideViewPosition/"
                        "translation(2): error.expected.jsnumber"
                    ),
                },
                id="guide-view-position-translation-element-not-number",
            ),
        ],
    )
    def test_invalid_dataset_request(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        body: dict[str, object],
        expected_messages: set[str],
    ) -> None:
        """Invalid standard dataset creation requests are rejected."""
        credentials = _credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = _get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.post(
            url=f"{_VWS_HOST}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
            timeout=30,
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "BAD_REQUEST"
        assert error["message"] == (
            f"Validation error for request {error['target']}"
        )
        actual_messages = {detail["message"] for detail in error["details"]}
        assert actual_messages == expected_messages
        for detail in error["details"]:
            assert detail["code"] == "VALIDATION_ERROR"

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
        verify_model_target_mock_vuforia: VuforiaBackend,
        method: HTTPMethod,
        path: str,
    ) -> None:
        """Unknown datasets are rejected with a NOT_FOUND error."""
        credentials = _credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = _get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.request(
            method=method,
            url=f"{_VWS_HOST}{path}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        error = response.json()["error"]
        assert error["code"] == "NOT_FOUND"
        assert error["message"] == (
            f"Could not find a model-view database with uuid {_DATASET_UUID}"
        )
        # The user-id portion is per-account in real Vuforia, so check only
        # the stable prefix.
        assert error["target"].startswith("userId:")


class TestMockOnlyErrors:
    """Mock-only Model Target Web API error paths.

    These cases cannot easily be verified against real Vuforia with the
    currently available test account and are kept mock-only by design.
    """

    @staticmethod
    def test_advanced_model_count_exceeds_limit() -> None:
        """Advanced dataset requests with too many models are rejected.

        Real Vuforia returns a 403 for the currently available test account
        because the account lacks the advanced-dataset scope, so the
        validation-error shape cannot be observed end-to-end. The mock
        therefore enforces the documented advanced-dataset model count
        limit on its own.
        """
        body = {
            **_UNAUTHENTICATED_DATASET_REQUEST,
            "models": [*_UNAUTHENTICATED_DATASET_REQUEST["models"]] * 21,
        }
        with MockVWS():
            response = requests.post(
                url=f"{_VWS_HOST}/modeltargets/advancedDatasets",
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                json=body,
                timeout=30,
            )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "BAD_REQUEST"
        assert error["details"][0]["code"] == "VALIDATION_ERROR"

    @staticmethod
    def test_processing_dataset_cannot_be_downloaded() -> None:
        """A dataset cannot be downloaded while it is still processing.

        Mock-only because exercising this against real Vuforia would require
        creating a dataset on every test run; the mock lets us drive the
        processing window deterministically.
        """
        with MockVWS(processing_time_seconds=60):
            create_response = requests.post(
                url=f"{_VWS_HOST}/modeltargets/datasets",
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                json=_UNAUTHENTICATED_DATASET_REQUEST,
                timeout=30,
            )
            dataset_uuid = create_response.json()["uuid"]
            response = requests.get(
                url=(
                    f"{_VWS_HOST}/modeltargets/datasets/{dataset_uuid}/dataset"
                ),
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                timeout=30,
            )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        error = response.json()["error"]
        assert error["code"] == "UNSUPPORTED_STATE"
        assert error["message"] == (
            f"Training status for dataset {dataset_uuid} is "
            "not-started != done"
        )
        assert error["target"] == dataset_uuid

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("created_path", "other_path"),
        argvalues=[
            pytest.param(
                "/modeltargets/datasets",
                "/modeltargets/advancedDatasets",
                id="standard-dataset-via-advanced-routes",
            ),
            pytest.param(
                "/modeltargets/advancedDatasets",
                "/modeltargets/datasets",
                id="advanced-dataset-via-standard-routes",
            ),
        ],
    )
    def test_dataset_is_not_visible_to_the_other_dataset_type(
        *,
        created_path: str,
        other_path: str,
    ) -> None:
        """A dataset is not reachable through the other type's routes.

        Standard and advanced datasets are separate resources in real
        Vuforia, with separate OAuth scopes. This is mock-only because the
        available test account lacks the advanced-dataset scope, so real
        Vuforia rejects advanced routes with a 403 before looking a dataset
        up.
        """
        headers = {"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"}
        with MockVWS():
            create_response = requests.post(
                url=f"{_VWS_HOST}{created_path}",
                headers=headers,
                json=_UNAUTHENTICATED_DATASET_REQUEST,
                timeout=30,
            )
            assert create_response.status_code == HTTPStatus.CREATED
            dataset_uuid = create_response.json()["uuid"]

            other_responses = [
                requests.get(
                    url=f"{_VWS_HOST}{other_path}/{dataset_uuid}/status",
                    headers=headers,
                    timeout=30,
                ),
                requests.get(
                    url=f"{_VWS_HOST}{other_path}/{dataset_uuid}/dataset",
                    headers=headers,
                    timeout=30,
                ),
                requests.delete(
                    url=f"{_VWS_HOST}{other_path}/{dataset_uuid}",
                    headers=headers,
                    timeout=30,
                ),
            ]

            # The dataset survives the delete attempt made through the other
            # type's routes.
            own_status_response = requests.get(
                url=f"{_VWS_HOST}{created_path}/{dataset_uuid}/status",
                headers=headers,
                timeout=30,
            )

        for response in other_responses:
            assert response.status_code == HTTPStatus.NOT_FOUND
            error = response.json()["error"]
            assert error["code"] == "NOT_FOUND"
            assert error["message"] == (
                "Could not find a model-view database with uuid "
                f"{dataset_uuid}"
            )
            assert error["target"].startswith("userId:")

        assert own_status_response.status_code == HTTPStatus.OK


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
        access_token = _get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
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

    @staticmethod
    def test_create_with_cad_data_blob(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """A dataset can be created with inline CAD data."""
        credentials = _credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = _get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        headers = {"Authorization": f"Bearer {access_token}"}

        create_response = requests.post(
            url=f"{_VWS_HOST}/modeltargets/datasets",
            headers=headers,
            json=_blob_dataset_request(),
            timeout=30,
        )

        assert create_response.status_code == HTTPStatus.CREATED
        create_response_json: dict[str, Any] = json.loads(
            s=create_response.text,
        )
        dataset_uuid = create_response_json["uuid"]
        assert isinstance(dataset_uuid, str)

        # There is nothing to assert between creating and deleting the
        # dataset, so the delete does not need a ``finally`` block to avoid
        # leaving a dataset behind on real Vuforia.
        delete_response = requests.delete(
            url=f"{_VWS_HOST}/modeltargets/datasets/{dataset_uuid}",
            headers=headers,
            timeout=30,
        )
        assert delete_response.status_code in {
            HTTPStatus.OK,
            HTTPStatus.NO_CONTENT,
        }


class TestModelTargetDatasetStatus:
    """Tests for Model Target dataset status response bodies."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("processing_time_seconds", "status", "time_field"),
        argvalues=[
            pytest.param(3600.0, "processing", "eta", id="processing"),
            pytest.param(0.0, "done", "completedAt", id="done"),
        ],
    )
    def test_status_uses_matching_time_field(
        *,
        processing_time_seconds: float,
        status: str,
        time_field: str,
    ) -> None:
        """Each status includes only its matching timestamp field."""
        dataset = ModelTargetDataset(
            request_body={},
            dataset_type=ModelTargetDatasetType.STANDARD,
            processing_time_seconds=processing_time_seconds,
            generation_failure=None,
            generation_warning=None,
            uuid_="dataset-uuid",
        )

        body = dataset.status_body()

        assert body["status"] == status
        assert body["uuid"] == "dataset-uuid"
        assert {"eta", "completedAt"} & body.keys() == {time_field}
