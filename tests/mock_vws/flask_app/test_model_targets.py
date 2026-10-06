"""Tests for model targets through the Flask app."""

import io
import uuid
import zipfile
from http import HTTPStatus

import pytest
import requests
from pydantic import TypeAdapter

from mock_vws.model_target import (
    JSONValue,
    ModelTargetDataset,
    ModelTargetDatasetType,
    ModelTargetGenerationFailure,
    ModelTargetGenerationWarning,
)
from tests.mock_vws.flask_app.helpers import EXAMPLE_URL_FOR_TARGET_MANAGER

_MODEL_TARGET_DATASET_REQUEST: dict[str, JSONValue] = {
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


class TestModelTargetWebAPI:
    """Tests for the Model Target Web API through the Flask app."""

    @staticmethod
    def test_standard_dataset_workflow(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A Model Target dataset can be created and downloaded."""
        monkeypatch.setenv(name="PROCESSING_TIME_SECONDS", value="0")
        token_response = requests.post(
            url="https://vws.vuforia.com/oauth2/token",
            auth=("client-id", "client-secret"),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        token_body = TypeAdapter(type=dict[str, JSONValue]).validate_python(
            token_response.json(),
        )
        token = token_body["access_token"]
        assert isinstance(token, str)
        headers = {"Authorization": f"Bearer {token}"}

        create_response = requests.post(
            url="https://vws.vuforia.com/modeltargets/datasets",
            headers=headers,
            json=_MODEL_TARGET_DATASET_REQUEST,
            timeout=30,
        )
        create_body = TypeAdapter(type=dict[str, JSONValue]).validate_python(
            create_response.json(),
        )
        dataset_uuid = create_body["uuid"]
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

    @staticmethod
    def _dataset_status(dataset_uuid: str) -> dict[str, JSONValue]:
        """Return a dataset's status response body from the VWS app."""
        token_response = requests.post(
            url="https://vws.vuforia.com/oauth2/token",
            auth=("client-id", "client-secret"),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        token_body = TypeAdapter(type=dict[str, JSONValue]).validate_python(
            token_response.json(),
        )
        token = token_body["access_token"]
        assert isinstance(token, str)
        status_response = requests.get(
            url=(
                "https://vws.vuforia.com/modeltargets/datasets/"
                f"{dataset_uuid}/status"
            ),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        assert status_response.status_code == HTTPStatus.OK
        return TypeAdapter(type=dict[str, JSONValue]).validate_python(
            status_response.json(),
        )

    def test_seeded_generation_failure(self) -> None:
        """A dataset seeded with a generation failure through the target
        manager API reports the failure through the VWS app.
        """
        dataset = ModelTargetDataset(
            request_body=_MODEL_TARGET_DATASET_REQUEST,
            dataset_type=ModelTargetDatasetType.STANDARD,
            processing_time_seconds=0.0,
            generation_failure=ModelTargetGenerationFailure(
                message="Seeded failure",
            ),
            generation_warning=None,
        )
        datasets_url = (
            EXAMPLE_URL_FOR_TARGET_MANAGER + "/model_target_datasets"
        )
        create_response = requests.post(
            url=datasets_url,
            json=dataset.to_dict(),
            timeout=30,
        )

        assert create_response.status_code == HTTPStatus.CREATED
        status_body = self._dataset_status(dataset_uuid=dataset.uuid_)
        assert status_body["status"] == "failed"
        error = status_body["error"]
        assert isinstance(error, dict)
        assert error["message"] == "Seeded failure"

    def test_seeded_generation_warning(self) -> None:
        """A dataset seeded with a generation warning through the target
        manager API reports the warning through the VWS app.
        """
        dataset = ModelTargetDataset(
            request_body=_MODEL_TARGET_DATASET_REQUEST,
            dataset_type=ModelTargetDatasetType.STANDARD,
            processing_time_seconds=0.0,
            generation_failure=None,
            generation_warning=ModelTargetGenerationWarning(
                message="Seeded warning",
            ),
        )
        datasets_url = (
            EXAMPLE_URL_FOR_TARGET_MANAGER + "/model_target_datasets"
        )
        create_response = requests.post(
            url=datasets_url,
            json=dataset.to_dict(),
            timeout=30,
        )

        assert create_response.status_code == HTTPStatus.CREATED
        status_body = self._dataset_status(dataset_uuid=dataset.uuid_)
        assert status_body["status"] == "done"
        warning = status_body["warning"]
        assert isinstance(warning, dict)
        assert warning["message"] == "Seeded warning"

    @staticmethod
    def test_delete_unknown_dataset() -> None:
        """Deleting an unknown dataset from the target manager returns a
        404 response.
        """
        datasets_url = (
            EXAMPLE_URL_FOR_TARGET_MANAGER + "/model_target_datasets"
        )
        delete_response = requests.delete(
            url=datasets_url + "/" + uuid.uuid4().hex,
            timeout=30,
        )

        assert delete_response.status_code == HTTPStatus.NOT_FOUND
