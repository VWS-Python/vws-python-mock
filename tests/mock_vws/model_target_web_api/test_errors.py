"""Tests for errors through the Model Target Web API.

Tests for the Model Target status assertion helper.

The helper exists to make real Vuforia failures legible, so its
messages are worth testing.
"""

import base64
from collections.abc import Set as AbstractSet
from http import HTTPMethod, HTTPStatus

import pytest
import requests
from beartype import beartype
from vws.response import Response

from tests.mock_vws.fixtures.model_target_prepared_requests import (
    MODEL_TARGET_DATASET_UUID,
    credentials_for_backend,
    get_access_token,
)
from tests.mock_vws.fixtures.vuforia_backends import (
    VuforiaBackend,
)
from tests.mock_vws.model_target_web_api.assertions import assert_oauth2_error
from tests.mock_vws.model_target_web_api.authentication import VWS_HOST
from tests.mock_vws.model_target_web_api.responses import (
    response_targeted_error,
    response_validation_error,
)
from tests.mock_vws.model_target_web_api.sample_data import (
    MODEL,
    UNAUTHENTICATED_DATASET_REQUEST,
    VIEW,
)
from tests.mock_vws.utils.assertions import (
    assert_model_target_status,
)

_MODEL_WITHOUT_CAD_DATA: dict[str, object] = {
    key: value for key, value in MODEL.items() if key != "cadDataUrl"
}

_EMPTY_MODEL: dict[str, object] = {}

_EMPTY_VIEW: dict[str, object] = {}

_EMPTY_GUIDE_VIEW_POSITION: list[object] = []

_EMPTY_GUIDE_VIEW_POSITION_OBJECT: dict[str, object] = {}


@beartype
def _fake_response(
    *,
    status_code: HTTPStatus,
    text: str,
    url: str,
) -> Response:
    """Return a response for testing the status assertion helper."""
    return Response(
        text=text,
        url=url,
        status_code=status_code,
        headers={},
        request_body=None,
        tell_position=len(text),
        content=text.encode(encoding="utf-8"),
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
            url=f"{VWS_HOST}/oauth2/token",
            headers={"Authorization": authorization},
            data={"grant_type": "client_credentials"},
            timeout=30,
        )

        assert_oauth2_error(
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
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [],
                },
                {"exactly one model should be provided"},
                id="standard-zero-models",
            ),
            pytest.param(
                {**UNAUTHENTICATED_DATASET_REQUEST, "name": 1},
                {"/name: error.expected.jsstring"},
                id="name-not-string",
            ),
            pytest.param(
                {**UNAUTHENTICATED_DATASET_REQUEST, "targetSdk": ["10.18"]},
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
                {**UNAUTHENTICATED_DATASET_REQUEST, "models": ["model"]},
                {
                    "/models(0)/name: element is required",
                    "/models(0)/views: element is required",
                },
                id="model-not-object",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [MODEL, "model"],
                },
                {
                    "/models(1)/name: element is required",
                    "/models(1)/views: element is required",
                },
                id="second-model-not-object",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [_EMPTY_MODEL],
                },
                {
                    "/models(0)/name: element is required",
                    "/models(0)/views: element is required",
                },
                id="model-missing-fields",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [_MODEL_WITHOUT_CAD_DATA],
                },
                {
                    (
                        "model 'model-name' is invalid. One of `cadDataBlob`, "
                        "`cadDataUrl`, `cadDataUuid` need to be provided"
                    ),
                },
                id="model-without-cad-data",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **MODEL,
                            "cadDataBlob": "ZmFrZQ==",
                            "cadDataFormat": "ZIP",
                        },
                    ],
                },
                {
                    (
                        "model 'model-name' is invalid. Only one of "
                        "`cadDataBlob`, `cadDataUrl`, `cadDataUuid` need to "
                        "be provided"
                    ),
                },
                id="model-with-both-cad-data-sources",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **MODEL,
                            "cadDataUrl": 1,
                        },
                    ],
                },
                {"/models(0)/cadDataUrl: error.expected.jsstring"},
                id="model-cad-data-url-not-string",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
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
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "cadDataFormat": 1}],
                },
                {"/models(0)/cadDataFormat: error.expected.jsstring"},
                id="model-cad-data-format-not-string",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "cadDataFormat": "gltf"}],
                },
                {
                    (
                        "Unrecognized cadDataFormat 'GLTF'.  Allowed values "
                        "are: ZIP, GLB, DRC_GLB, DRC_GLTF, DAE, FBX, IGES, "
                        "OBJ, PVS, PVZ, STL, VRML, or specify no "
                        "cadDataFormat to auto-detect GLB and zipped glTFs."
                    ),
                },
                id="model-cad-data-format-not-in-enum",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "name": None}],
                },
                {"/models(0)/name: error.expected.jsstring"},
                id="model-name-not-string",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "simplify": 1}],
                },
                {"/models(0)/simplify: error.expected.jsstring"},
                id="model-simplify-not-string",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "simplify": "sometimes"}],
                },
                {
                    (
                        "invalid simplify. Should be one of 'never', "
                        "'always', 'auto'. You provided 'Some(sometimes)'"
                    ),
                },
                id="model-simplify-not-in-enum",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "automaticColoring": "sometimes"}],
                },
                {
                    (
                        "invalid automaticColoring. Should be one of 'never', "
                        "'always', 'auto'. You provided 'sometimes'"
                    ),
                },
                id="model-automatic-coloring-not-in-enum",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "motionHint": "still"}],
                },
                {
                    (
                        "`motionHint` and `trackingMode` are no longer "
                        "supported when using `targetsSdk` 10.9 or later. "
                        "Please use the `optimizeTrackingFor` setting instead."
                    ),
                },
                id="model-motion-hint-not-in-enum",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "optimizeTrackingFor": "cars"}],
                },
                {
                    (
                        "`optimizeTrackingFor` must be one of "
                        "default,low_feature_objects,ar_controller"
                    ),
                },
                id="model-optimize-tracking-for-not-in-enum",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "trackingMode": "boat"}],
                },
                {
                    (
                        "`motionHint` and `trackingMode` are no longer "
                        "supported when using `targetsSdk` 10.9 or later. "
                        "Please use the `optimizeTrackingFor` setting instead."
                    ),
                },
                id="model-tracking-mode-not-in-enum",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **MODEL,
                            "motionHint": "still",
                            "simplify": "sometimes",
                        },
                    ],
                },
                {
                    (
                        "`motionHint` and `trackingMode` are no longer "
                        "supported when using `targetsSdk` 10.9 or later. "
                        "Please use the `optimizeTrackingFor` setting instead."
                    ),
                    (
                        "invalid simplify. Should be one of 'never', "
                        "'always', 'auto'. You provided 'Some(sometimes)'"
                    ),
                },
                id="model-multiple-enum-errors",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "views": "view-name"}],
                },
                {"/models(0)/views: error.expected.jsarray"},
                id="model-views-not-array",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "views": ["view-name"]}],
                },
                {"/models(0)/views(0)/name: element is required"},
                id="view-not-object",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**MODEL, "views": [_EMPTY_VIEW]}],
                },
                {"/models(0)/views(0)/name: element is required"},
                id="view-missing-fields",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {**MODEL, "views": [{**VIEW, "name": 1}]},
                    ],
                },
                {"/models(0)/views(0)/name: error.expected.jsstring"},
                id="view-name-not-string",
            ),
            pytest.param(
                {
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **MODEL,
                            "views": [
                                VIEW,
                                {
                                    **VIEW,
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
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **MODEL,
                            "views": [
                                {
                                    **VIEW,
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
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **MODEL,
                            "views": [
                                {
                                    **VIEW,
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
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **MODEL,
                            "views": [
                                {
                                    **VIEW,
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
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **MODEL,
                            "views": [
                                {
                                    **VIEW,
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
                    **UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **MODEL,
                            "views": [
                                {
                                    **VIEW,
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
            url=f"{VWS_HOST}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
            timeout=30,
        )

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
        error = response_validation_error(response=response)
        assert error["code"] == "BAD_REQUEST"
        assert error["message"] == (
            f"Validation error for request {error['target']}"
        )
        actual_messages = {detail["message"] for detail in error["details"]}
        assert actual_messages == expected_messages
        for detail in error["details"]:
            assert detail["code"] == "VALIDATION_ERROR"

    @staticmethod
    def test_advanced_model_count_exceeds_limit(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """Advanced datasets reject more than 20 uniquely named models."""
        models = [{**MODEL, "name": f"model-{index}"} for index in range(21)]
        # Include a duplicate to verify the two validation details which real
        # Vuforia returns together for this request.
        models[-1]["name"] = models[0]["name"]
        body = {**UNAUTHENTICATED_DATASET_REQUEST, "models": models}
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.post(
            url=f"{VWS_HOST}/modeltargets/advancedDatasets",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
            timeout=30,
        )

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
        error = response_validation_error(response=response)
        assert error["code"] == "BAD_REQUEST"
        assert {detail["message"] for detail in error["details"]} == {
            "names of models must be unique within a Target.",
            "total number of models must be maximum 20",
        }
        assert all(
            detail["code"] == "VALIDATION_ERROR" for detail in error["details"]
        )

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
            url=f"{VWS_HOST}{path}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.NOT_FOUND,
        )
        error = response_targeted_error(response=response)
        assert error["code"] == "NOT_FOUND"
        assert error["message"] == (
            "Could not find a model-view database with uuid "
            f"{MODEL_TARGET_DATASET_UUID}"
        )
        # The user-id portion is per-account in real Vuforia, so check only
        # the stable prefix.
        assert error["target"].startswith("userId:")


@pytest.mark.parametrize(
    argnames="status_codes",
    argvalues=[
        pytest.param(HTTPStatus.OK, id="single"),
        pytest.param(
            {HTTPStatus.OK, HTTPStatus.NO_CONTENT},
            id="set",
        ),
    ],
)
def test_expected_status(
    *,
    status_codes: HTTPStatus | AbstractSet[HTTPStatus],
) -> None:
    """An expected status code does not raise."""
    response = _fake_response(
        status_code=HTTPStatus.OK,
        text="{}",
        url=f"{VWS_HOST}/modeltargets/advancedDatasets",
    )
    assert_model_target_status(
        response=response,
        status_codes=status_codes,
    )


def test_unexpected_status_shows_the_body() -> None:
    """An unexpected status code reports the URL and the body."""
    text = '{"error":{"code":"VALIDATION_ERROR"}}'
    response = _fake_response(
        status_code=HTTPStatus.BAD_REQUEST,
        text=text,
        url=f"{VWS_HOST}/modeltargets/advancedDatasets",
    )
    with pytest.raises(expected_exception=AssertionError) as exc:
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.CREATED,
        )

    message = str(object=exc.value)
    assert message == (
        "Expected 201 CREATED from "
        f"{VWS_HOST}/modeltargets/advancedDatasets, got 400.\n"
        f"\nResponse body:\n{text}"
    )


def test_multiple_expected_statuses() -> None:
    """Every expected status code is named in the message."""
    response = _fake_response(
        status_code=HTTPStatus.BAD_REQUEST,
        text="{}",
        url=f"{VWS_HOST}/modeltargets/advancedDatasets",
    )
    with pytest.raises(expected_exception=AssertionError) as exc:
        assert_model_target_status(
            response=response,
            status_codes={HTTPStatus.OK, HTTPStatus.NO_CONTENT},
        )

    assert "Expected 200 OK or 204 NO_CONTENT from " in str(object=exc.value)


def test_training_allowance_exceeded() -> None:
    """An exhausted account allowance is an expected failure, called
    out as such in the first line so that a truncated CI summary
    still shows it.
    """
    response = _fake_response(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        text=(
            '{"error":{"code":"TRAINING_ALLOWANCE_EXCEEDED",'
            '"message":"Signing quota reached","target":"7635391"}}'
        ),
        url="http://example.com/modeltargets/datasets",
    )
    with pytest.raises(expected_exception=pytest.xfail.Exception) as exc:
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.CREATED,
        )

    message = str(object=exc.value)
    first_line = message.splitlines()[0]
    assert first_line == (
        "The Vuforia account is out of Model Target training allowance - "
        "this is not a failure of the code under test."
    )
    assert "MODEL_TARGET_VUFORIA_CLIENT_ID" in message
    assert "has to be raised, or reset, on the Vuforia account" in message
    assert "expected failure" in message
