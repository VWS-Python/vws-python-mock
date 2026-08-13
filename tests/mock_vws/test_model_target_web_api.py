"""Verified fake tests for the Model Target Web API."""

import base64
import dataclasses
import io
import json
import zipfile
from http import HTTPMethod, HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
import requests
from beartype import beartype
from vws.response import Response

from mock_vws import MockVWS
from mock_vws.model_target import ModelTargetDataset, ModelTargetDatasetType
from tests.mock_vws.fixtures.model_target_prepared_requests import (
    MODEL_TARGET_DATASET_UUID,
    credentials_for_backend,
    get_access_token,
)
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.utils import ModelTargetEndpoint

_VWS_HOST = "https://vws.vuforia.com"
_MOCK_BEARER_TOKEN = "eyJhbGciOiJtb2NrIn0.e30.c2lnbmF0dXJl"


_VIEW: dict[str, Any] = {
    "name": "view-name",
    "guideViewPosition": {
        "translation": [0, 0, 5],
        "rotation": [0, 0, 0, 1],
    },
}


@beartype
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


@beartype
def _cad_data_blob() -> str:
    """Return a base64-encoded zipped model for inline CAD data."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(file=zip_buffer, mode="w") as zip_file:
        zip_file.writestr(
            zinfo_or_arcname="model.gltf",
            data=json.dumps(obj={"asset": {"version": "2.0"}}),
        )
    return base64.b64encode(s=zip_buffer.getvalue()).decode(encoding="ascii")


@beartype
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

_STATE_CONFIGURATION = json.dumps(
    obj={
        "version": "1.0",
        "default_state": "assembled",
        "states": {
            "assembled": {"base_scene": 0},
            "disassembled": {"base_scene": 0},
        },
    },
)


@beartype
def _assert_oauth2_error(
    *,
    response: requests.Response,
    status_code: HTTPStatus,
    body: dict[str, str],
) -> None:
    """Assert an OAuth2 error response."""
    assert response.status_code == status_code
    assert response.json() == body


@beartype
def _assert_model_target_error(
    *,
    response: Response,
    status_code: HTTPStatus,
    code: str,
    message: str,
    target: str,
) -> None:
    """Assert a Model Target Web API error response with the legacy
    shape.
    """
    assert response.status_code == status_code
    assert json.loads(s=response.text) == {
        "error": {
            "code": code,
            "message": message,
            "target": target,
        },
    }


@beartype
def _assert_unknown_dataset(*, response: Response) -> None:
    """Assert a NOT_FOUND error for the unknown dataset UUID which the
    prepared requests use.

    The body-less Model Target endpoints ignore any request body, so a
    request with a valid bearer token and an unexpected or malformed body
    reaches the dataset lookup.
    """
    assert response.status_code == HTTPStatus.NOT_FOUND
    error = json.loads(s=response.text)["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message"] == (
        "Could not find a model-view database with uuid "
        f"{MODEL_TARGET_DATASET_UUID}"
    )
    # The user-id portion is per-account in real Vuforia, so check only
    # the stable prefix.
    assert error["target"].startswith("userId:")


@beartype
def _access_token_for_backend(*, backend: VuforiaBackend) -> str:
    """Return a valid access token for the chosen backend."""
    credentials = credentials_for_backend(backend=backend)
    return get_access_token(credentials=credentials, backend=backend)


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
class TestAuthentication:
    """Tests for Model Target Web API authentication.

    Bearer token concerns which apply to every Model Target endpoint are
    covered by ``TestAuthorizationHeader``, via the
    ``model_target_endpoint`` fixture.
    """

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
class TestAuthorizationHeader:
    """Tests for the ``Authorization`` header on every Model Target
    endpoint.

    These mirror the cross-cutting tests which the ``endpoint`` fixture
    supports for the VWS and Query APIs. The Model Target Web API uses
    OAuth2 bearer tokens rather than HMAC signatures, so the VWS
    ``Authorization`` and ``Date`` header concerns do not apply to it,
    and it gets its own smaller set of concerns via the
    ``model_target_endpoint`` fixture. The OAuth2 token endpoint is not
    in that fixture because it takes HTTP Basic credentials rather than
    a bearer token.
    """

    @staticmethod
    def test_missing(
        *,
        model_target_endpoint: ModelTargetEndpoint,
    ) -> None:
        """An ``UNAUTHORIZED`` response is returned when no
        ``Authorization`` header is given.
        """
        response = model_target_endpoint.send()

        _assert_model_target_error(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message="no Bearer token",
            target="jwt",
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("authorization", "message"),
        argvalues=[
            pytest.param("Basic abc", "no Bearer token", id="not-bearer"),
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
        model_target_endpoint: ModelTargetEndpoint,
        authorization: str,
        message: str,
    ) -> None:
        """Invalid bearer tokens are rejected."""
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers={
                **model_target_endpoint.headers,
                "Authorization": authorization,
            },
        )

        response = new_endpoint.send()

        _assert_model_target_error(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message=message,
            target="jwt",
        )


class TestInvalidJson:
    """Tests for giving Model Target endpoints bodies which are not
    valid JSON objects.
    """

    @staticmethod
    def test_wrong_content_type(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        model_target_endpoint: ModelTargetEndpoint,
    ) -> None:
        """Requests without a JSON content type are rejected with 415 by
        endpoints which read a body, and are unaffected elsewhere.
        """
        access_token = _access_token_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        new_headers = {
            **model_target_endpoint.headers,
            "Authorization": f"Bearer {access_token}",
        }
        new_headers.pop("Content-Type", None)
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers=new_headers,
        )

        response = new_endpoint.send()

        if not model_target_endpoint.takes_json_body:
            _assert_unknown_dataset(response=response)
            return

        assert response.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
        error = json.loads(s=response.text)["error"]
        assert error["code"] == "ERROR"
        assert error["message"] == (
            "Expecting text/json or application/json body"
        )
        assert "target" not in error

    @staticmethod
    def test_invalid_json(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        model_target_endpoint: ModelTargetEndpoint,
    ) -> None:
        """Malformed JSON bodies are rejected with 400 by endpoints which
        read a body, and are ignored elsewhere.
        """
        access_token = _access_token_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        content = b"{"
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers={
                **model_target_endpoint.headers,
                "Authorization": f"Bearer {access_token}",
                "Content-Length": str(object=len(content)),
            },
            data=content,
        )

        response = new_endpoint.send()

        if not model_target_endpoint.takes_json_body:
            _assert_unknown_dataset(response=response)
            return

        assert response.status_code == HTTPStatus.BAD_REQUEST
        error = json.loads(s=response.text)["error"]
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
        model_target_endpoint: ModelTargetEndpoint,
        body: str,
    ) -> None:
        """JSON bodies which are not objects are missing every field on
        endpoints which read a body, and are ignored elsewhere.
        """
        access_token = _access_token_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        content = body.encode(encoding="utf-8")
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers={
                **model_target_endpoint.headers,
                "Authorization": f"Bearer {access_token}",
                "Content-Length": str(object=len(content)),
            },
            data=content,
        )

        response = new_endpoint.send()

        if not model_target_endpoint.takes_json_body:
            _assert_unknown_dataset(response=response)
            return

        assert response.status_code == HTTPStatus.BAD_REQUEST
        error = json.loads(s=response.text)["error"]
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
                    "models": [{**_MODEL, "simplify": 1}],
                },
                {"/models(0)/simplify: error.expected.jsstring"},
                id="model-simplify-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "simplify": "sometimes"}],
                },
                {"/models(0)/simplify: error.expected.validenum"},
                id="model-simplify-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "automaticColoring": "sometimes"}],
                },
                {"/models(0)/automaticColoring: error.expected.validenum"},
                id="model-automatic-coloring-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "motionHint": "still"}],
                },
                {"/models(0)/motionHint: error.expected.validenum"},
                id="model-motion-hint-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "optimizeTrackingFor": "cars"}],
                },
                {"/models(0)/optimizeTrackingFor: error.expected.validenum"},
                id="model-optimize-tracking-for-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "trackingMode": "boat"}],
                },
                {"/models(0)/trackingMode: error.expected.validenum"},
                id="model-tracking-mode-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "motionHint": "still",
                            "simplify": "sometimes",
                        },
                    ],
                },
                {
                    "/models(0)/motionHint: error.expected.validenum",
                    "/models(0)/simplify: error.expected.validenum",
                },
                id="model-multiple-enum-errors",
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
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = get_access_token(
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
                f"/modeltargets/datasets/{MODEL_TARGET_DATASET_UUID}/status",
                id="status",
            ),
            pytest.param(
                HTTPMethod.GET,
                f"/modeltargets/datasets/{MODEL_TARGET_DATASET_UUID}/dataset",
                id="download",
            ),
            pytest.param(
                HTTPMethod.DELETE,
                f"/modeltargets/datasets/{MODEL_TARGET_DATASET_UUID}",
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
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = get_access_token(
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
            "Could not find a model-view database with uuid "
            f"{MODEL_TARGET_DATASET_UUID}"
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
    @pytest.mark.parametrize(
        argnames="dataset_path",
        argvalues=[
            pytest.param("/modeltargets/datasets", id="standard"),
            pytest.param(
                "/modeltargets/advancedDatasets",
                id="advanced",
            ),
        ],
    )
    @pytest.mark.parametrize(
        argnames="view_updates",
        argvalues=[
            pytest.param({}, id="all-states"),
            pytest.param(
                {"states": ["assembled"]},
                id="selected-states",
            ),
        ],
    )
    def test_state_based_dataset(
        *,
        model_target_mock_only_vuforia: VuforiaBackend,
        dataset_path: str,
        view_updates: dict[str, object],
    ) -> None:
        """State-Based Model Target fields survive a dataset round
        trip.
        """
        body = {
            **_UNAUTHENTICATED_DATASET_REQUEST,
            "models": [
                {
                    **_MODEL,
                    "stateBasedConfigurationJsonString": (
                        _STATE_CONFIGURATION
                    ),
                    "views": [{**_VIEW, **view_updates}],
                },
            ],
        }
        access_token = _access_token_for_backend(
            backend=model_target_mock_only_vuforia,
        )
        headers = {"Authorization": f"Bearer {access_token}"}
        create_response = requests.post(
            url=f"{_VWS_HOST}{dataset_path}",
            headers=headers,
            json=body,
            timeout=30,
        )

        assert create_response.status_code == HTTPStatus.CREATED
        dataset_uuid = create_response.json()["uuid"]
        delete_response = requests.delete(
            url=f"{_VWS_HOST}{dataset_path}/{dataset_uuid}",
            headers=headers,
            timeout=30,
        )
        assert delete_response.status_code == HTTPStatus.OK

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("model_updates", "view_updates", "expected_message"),
        argvalues=[
            pytest.param(
                {"stateBasedConfigurationJsonString": 1},
                {},
                (
                    "/models(0)/stateBasedConfigurationJsonString: "
                    "error.expected.jsstring"
                ),
                id="configuration-not-string",
            ),
            pytest.param(
                {"stateBasedConfigurationJsonString": "{"},
                {},
                (
                    "/models(0)/stateBasedConfigurationJsonString: "
                    "error.expected.validjson"
                ),
                id="configuration-not-json",
            ),
            pytest.param(
                {"stateBasedConfigurationJsonString": "{}"},
                {},
                (
                    "/models(0)/stateBasedConfigurationJsonString/states: "
                    "error.expected.jsobject"
                ),
                id="configuration-states-not-object",
            ),
            pytest.param(
                {"stateBasedConfigurationJsonString": "[]"},
                {},
                (
                    "/models(0)/stateBasedConfigurationJsonString/states: "
                    "error.expected.jsobject"
                ),
                id="configuration-not-object",
            ),
            pytest.param(
                {"stateBasedConfigurationJsonString": _STATE_CONFIGURATION},
                {"states": "assembled"},
                "/models(0)/views(0)/states: error.expected.jsarray",
                id="view-states-not-array",
            ),
            pytest.param(
                {"stateBasedConfigurationJsonString": _STATE_CONFIGURATION},
                {"states": ["assembled", 1]},
                ("/models(0)/views(0)/states(1): error.expected.jsstring"),
                id="view-state-not-string",
            ),
            pytest.param(
                {"stateBasedConfigurationJsonString": _STATE_CONFIGURATION},
                {"states": ["unknown"]},
                ("/models(0)/views(0)/states(0): error.expected.validenum"),
                id="view-state-not-declared",
            ),
            pytest.param(
                {},
                {"states": ["assembled"]},
                (
                    "/models(0)/stateBasedConfigurationJsonString: element "
                    "is required when view states are given"
                ),
                id="view-states-without-configuration",
            ),
        ],
    )
    def test_invalid_state_based_dataset(
        *,
        model_target_mock_only_vuforia: VuforiaBackend,
        model_updates: dict[str, object],
        view_updates: dict[str, object],
        expected_message: str,
    ) -> None:
        """Invalid State-Based Model Target fields are rejected."""
        body = {
            **_UNAUTHENTICATED_DATASET_REQUEST,
            "models": [
                {
                    **_MODEL,
                    **model_updates,
                    "views": [{**_VIEW, **view_updates}],
                },
            ],
        }
        access_token = _access_token_for_backend(
            backend=model_target_mock_only_vuforia,
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
        assert [detail["message"] for detail in error["details"]] == [
            expected_message,
        ]
        assert error["details"][0]["code"] == "VALIDATION_ERROR"

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
    def test_advanced_realistic_appearance_not_in_enum() -> None:
        """Advanced dataset requests with a ``realisticAppearance`` value
        outside the documented enumeration are rejected.

        The Model Target OpenAPI specification documents
        ``realisticAppearance`` as a model field for advanced datasets
        only, so standard dataset creation does not validate it. This is
        mock-only because the available test account lacks the
        advanced-dataset scope, so real Vuforia rejects the request with a
        403 before validating the body.
        """
        body = {
            **_UNAUTHENTICATED_DATASET_REQUEST,
            "models": [{**_MODEL, "realisticAppearance": "yes"}],
        }
        headers = {"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"}
        with MockVWS():
            advanced_response = requests.post(
                url=f"{_VWS_HOST}/modeltargets/advancedDatasets",
                headers=headers,
                json=body,
                timeout=30,
            )
            standard_response = requests.post(
                url=f"{_VWS_HOST}/modeltargets/datasets",
                headers=headers,
                json=body,
                timeout=30,
            )

        assert advanced_response.status_code == HTTPStatus.BAD_REQUEST
        error = advanced_response.json()["error"]
        assert error["code"] == "BAD_REQUEST"
        assert [detail["message"] for detail in error["details"]] == [
            "/models(0)/realisticAppearance: error.expected.validenum",
        ]
        assert error["details"][0]["code"] == "VALIDATION_ERROR"

        assert standard_response.status_code == HTTPStatus.CREATED

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
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = get_access_token(
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
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = get_access_token(
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
