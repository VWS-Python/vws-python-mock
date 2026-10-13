"""Tests for model targets through the `requests-mock` backend."""

import io
import zipfile
from http import HTTPStatus

import requests
from freezegun import freeze_time

from mock_vws import MockVWS, ModelTargetGenerationFailure
from tests.mock_vws.model_target_web_api.authentication import (
    MOCK_BEARER_TOKEN,
)
from tests.mock_vws.model_target_web_api.responses import (
    parse_response_json,
    response_targeted_error,
)
from tests.mock_vws.model_target_web_api.sample_data import (
    UNAUTHENTICATED_DATASET_REQUEST,
)
from tests.mock_vws.utils.assertions import assert_model_target_status

_MODEL_TARGET_AUTHORIZATION = (
    "Bearer eyJhbGciOiJtb2NrIn0."
    "eyJzY29wZSI6Im1vZGVsdGFyZ2V0cy5hbGwifQ."
    "c2lnbmF0dXJl"
)
_MODEL_TARGET_DATASET_REQUEST = {
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


def test_standard_dataset_workflow() -> None:
    """A standard Model Target dataset can be created and
    downloaded.
    """
    with MockVWS(processing_time_seconds=0):
        token_response = requests.post(
            url="https://vws.vuforia.com/oauth2/token",
            auth=("client-id", "client-secret"),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        token: object = token_response.json()["access_token"]
        assert isinstance(token, str)
        headers = {"Authorization": f"Bearer {token}"}

        create_response = requests.post(
            url="https://vws.vuforia.com/modeltargets/datasets",
            headers=headers,
            json=_MODEL_TARGET_DATASET_REQUEST,
            timeout=30,
        )
        dataset_uuid: object = create_response.json()["uuid"]
        assert isinstance(dataset_uuid, str)

        status_response = requests.get(
            url=(
                "https://vws.vuforia.com/modeltargets/datasets/"
                f"{dataset_uuid}/status"
            ),
            headers=headers,
            timeout=30,
        )
        dataset_response = requests.get(
            url=(
                "https://vws.vuforia.com/modeltargets/datasets/"
                f"{dataset_uuid}/dataset"
            ),
            headers=headers,
            timeout=30,
        )

    assert token_response.status_code == HTTPStatus.OK
    assert create_response.status_code == HTTPStatus.CREATED
    assert status_response.json()["status"] == "done"
    with zipfile.ZipFile(
        file=io.BytesIO(initial_bytes=dataset_response.content),
    ) as dataset_zip:
        assert dataset_zip.namelist() == ["MTDataset.dat", "MTDataset.xml"]


def test_advanced_dataset_workflow() -> None:
    """An advanced Model Target dataset can be created."""
    with MockVWS(processing_time_seconds=0):
        response = requests.post(
            url="https://vws.vuforia.com/modeltargets/advancedDatasets",
            headers={"Authorization": _MODEL_TARGET_AUTHORIZATION},
            json=_MODEL_TARGET_DATASET_REQUEST,
            timeout=30,
        )
        dataset_uuid: object = response.json()["uuid"]
        assert isinstance(dataset_uuid, str)
        status_response = requests.get(
            url=(
                "https://vws.vuforia.com/modeltargets/"
                f"advancedDatasets/{dataset_uuid}/status"
            ),
            headers={"Authorization": _MODEL_TARGET_AUTHORIZATION},
            timeout=30,
        )

    assert response.status_code == HTTPStatus.CREATED
    assert status_response.json()["uuid"] == dataset_uuid


def test_dataset_download_is_reproducible() -> None:
    """Downloading the same dataset produces identical bytes."""
    headers = {"Authorization": _MODEL_TARGET_AUTHORIZATION}
    with MockVWS(processing_time_seconds=0):
        with freeze_time(time_to_freeze="2026-01-01"):
            create_response = requests.post(
                url="https://vws.vuforia.com/modeltargets/datasets",
                headers=headers,
                json=_MODEL_TARGET_DATASET_REQUEST,
                timeout=30,
            )
        dataset_uuid: object = create_response.json()["uuid"]
        assert isinstance(dataset_uuid, str)
        dataset_url = (
            "https://vws.vuforia.com/modeltargets/datasets/"
            f"{dataset_uuid}/dataset"
        )
        with freeze_time(time_to_freeze="2026-01-02"):
            first_response = requests.get(
                url=dataset_url,
                headers=headers,
                timeout=30,
            )
        with freeze_time(time_to_freeze="2027-01-02"):
            second_response = requests.get(
                url=dataset_url,
                headers=headers,
                timeout=30,
            )

    assert first_response.status_code == HTTPStatus.OK
    assert second_response.status_code == HTTPStatus.OK
    assert first_response.content == second_response.content


def test_bearer_token_required() -> None:
    """Model Target dataset routes require a bearer token."""
    with MockVWS():
        response = requests.post(
            url="https://vws.vuforia.com/modeltargets/datasets",
            json=_MODEL_TARGET_DATASET_REQUEST,
            timeout=30,
        )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"] == {
        "code": "401",
        "message": "no Bearer token",
        "target": "jwt",
    }


def test_processing_dataset_cannot_be_downloaded(*, base_vws_url: str) -> None:
    """A dataset cannot be downloaded while it is still processing.

    Mock-only because exercising this against real Vuforia would require
    creating a dataset on every test run; the mock lets us drive the
    processing window deterministically.
    """
    with MockVWS(base_vws_url=base_vws_url, processing_time_seconds=60):
        create_response = requests.post(
            url=f"{base_vws_url}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            json=UNAUTHENTICATED_DATASET_REQUEST,
            timeout=30,
        )
        dataset_uuid = parse_response_json(response=create_response)["uuid"]
        assert isinstance(dataset_uuid, str)
        response = requests.get(
            url=(
                f"{base_vws_url}/modeltargets/datasets/{dataset_uuid}/dataset"
            ),
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            timeout=30,
        )

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.UNPROCESSABLE_ENTITY,
    )
    error = response_targeted_error(response=response)
    assert error["code"] == "UNSUPPORTED_STATE"
    assert error["message"] == (
        f"Training status for dataset {dataset_uuid} is not-started != done"
    )
    assert error["target"] == dataset_uuid


def test_failed_dataset_cannot_be_downloaded(*, base_vws_url: str) -> None:
    """A dataset which failed generation cannot be downloaded, and the
    error reports the failed training status rather than the
    ``not-started`` status which a still-processing dataset reports.

    Mock-only because a generation failure cannot be provoked on demand
    against real Vuforia, so the training status name it reports for a
    failed dataset has not been observed.
    """
    failure = ModelTargetGenerationFailure(message="CAD model is invalid")
    with MockVWS(
        base_vws_url=base_vws_url,
        processing_time_seconds=0,
        model_target_generation_failure=failure,
    ):
        create_response = requests.post(
            url=f"{base_vws_url}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            json=UNAUTHENTICATED_DATASET_REQUEST,
            timeout=30,
        )
        dataset_uuid = parse_response_json(response=create_response)["uuid"]
        assert isinstance(dataset_uuid, str)
        status_response = requests.get(
            url=f"{base_vws_url}/modeltargets/datasets/{dataset_uuid}/status",
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            timeout=30,
        )
        response = requests.get(
            url=(
                f"{base_vws_url}/modeltargets/datasets/{dataset_uuid}/dataset"
            ),
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            timeout=30,
        )

    assert status_response.json()["status"] == "failed"
    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.UNPROCESSABLE_ENTITY,
    )
    error = response_targeted_error(response=response)
    assert error["code"] == "UNSUPPORTED_STATE"
    assert error["message"] == (
        f"Training status for dataset {dataset_uuid} is failed != done"
    )
    assert error["target"] == dataset_uuid
