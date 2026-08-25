"""Tests for exhausted Model Target training allowance responses."""

from http import HTTPStatus
from typing import Any

import pytest
import requests

from mock_vws import MockVWS
from mock_vws._flask_server.vws import VWS_FLASK_APP

_AUTHORIZATION = (
    "Bearer eyJhbGciOiJtb2NrIn0."
    "eyJzY29wZSI6Im1vZGVsdGFyZ2V0cy5hbGwifQ."
    "c2lnbmF0dXJl"
)
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
_EXPECTED_BODY = {
    "error": {
        "code": "TRAINING_ALLOWANCE_EXCEEDED",
        "message": "User has reached total number of allowed trainings",
        "target": "userId:mock",
    },
}


@pytest.mark.parametrize(
    argnames="dataset_path",
    argvalues=[
        pytest.param("modeltargets/datasets", id="standard"),
        pytest.param("modeltargets/advancedDatasets", id="advanced"),
    ],
)
def test_requests_mock_training_allowance_exceeded(dataset_path: str) -> None:
    """The in-process mock can reject creation when allowance is spent."""
    with MockVWS(model_target_training_allowance_exceeded=True):
        response = requests.post(
            url=f"https://vws.vuforia.com/{dataset_path}",
            headers={"Authorization": _AUTHORIZATION},
            json=_REQUEST_BODY,
            timeout=30,
        )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == _EXPECTED_BODY


@pytest.mark.parametrize(
    argnames="dataset_path",
    argvalues=[
        pytest.param("/modeltargets/datasets", id="standard"),
        pytest.param("/modeltargets/advancedDatasets", id="advanced"),
    ],
)
def test_flask_training_allowance_exceeded(
    *,
    dataset_path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Flask mock supports the exhausted allowance configuration."""
    monkeypatch.setenv(
        name="MODEL_TARGET_TRAINING_ALLOWANCE_EXCEEDED",
        value="true",
    )
    monkeypatch.setenv(
        name="TARGET_MANAGER_BASE_URL",
        value="http://target-manager.example.com",
    )

    with VWS_FLASK_APP.test_client() as client:
        response = client.post(
            path=dataset_path,
            headers={"Authorization": _AUTHORIZATION},
            json=_REQUEST_BODY,
        )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json == _EXPECTED_BODY
