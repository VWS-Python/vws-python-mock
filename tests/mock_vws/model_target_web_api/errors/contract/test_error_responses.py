"""Verified fake tests for Model Target Web API error responses."""

import base64
from http import HTTPMethod, HTTPStatus

import pytest
import requests

from tests.mock_vws.fixtures.credentials import ModelTargetCredentials
from tests.mock_vws.fixtures.model_target_prepared_requests import (
    MODEL_TARGET_DATASET_UUID,
    get_access_token,
)
from tests.mock_vws.model_target_web_api.assertions import assert_oauth2_error
from tests.mock_vws.model_target_web_api.errors.helpers import (
    EMPTY_GUIDE_VIEW_POSITION,
    EMPTY_GUIDE_VIEW_POSITION_OBJECT,
    EMPTY_MODEL,
    EMPTY_VIEW,
    MODEL_WITHOUT_CAD_DATA,
)
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
def test_invalid_basic_auth_header(
    *, base_vws_url: str, authorization: str
) -> None:
    """Malformed OAuth2 Basic auth headers are rejected."""
    response = requests.post(
        url=f"{base_vws_url}/oauth2/token",
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
                "models": [EMPTY_MODEL],
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
                "models": [MODEL_WITHOUT_CAD_DATA],
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
                        **MODEL_WITHOUT_CAD_DATA,
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
                "models": [{**MODEL, "views": [EMPTY_VIEW]}],
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
                                    EMPTY_GUIDE_VIEW_POSITION
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
                                    EMPTY_GUIDE_VIEW_POSITION_OBJECT
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
    model_target_credentials: ModelTargetCredentials,
    base_vws_url: str,
    body: dict[str, object],
    expected_messages: set[str],
) -> None:
    """Invalid standard dataset creation requests are rejected."""
    access_token = get_access_token(
        base_vws_url=base_vws_url,
        credentials=model_target_credentials,
    )
    response = requests.post(
        url=f"{base_vws_url}/modeltargets/datasets",
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


def test_advanced_model_count_exceeds_limit(
    *,
    model_target_credentials: ModelTargetCredentials,
    base_vws_url: str,
) -> None:
    """Advanced datasets reject more than 20 uniquely named models."""
    models = [{**MODEL, "name": f"model-{index}"} for index in range(21)]
    # Include a duplicate to verify the two validation details which real
    # Vuforia returns together for this request.
    models[-1]["name"] = models[0]["name"]
    body = {**UNAUTHENTICATED_DATASET_REQUEST, "models": models}
    access_token = get_access_token(
        base_vws_url=base_vws_url,
        credentials=model_target_credentials,
    )
    response = requests.post(
        url=f"{base_vws_url}/modeltargets/advancedDatasets",
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
    model_target_credentials: ModelTargetCredentials,
    base_vws_url: str,
    method: HTTPMethod,
    path: str,
) -> None:
    """Unknown datasets are rejected with a NOT_FOUND error."""
    access_token = get_access_token(
        base_vws_url=base_vws_url,
        credentials=model_target_credentials,
    )
    response = requests.request(
        method=method,
        url=f"{base_vws_url}{path}",
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
