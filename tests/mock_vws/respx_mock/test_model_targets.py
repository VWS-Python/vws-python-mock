"""Tests for model targets through the `respx` mock.

Model Target Web API usage through the mock via ``httpx``.
"""

from http import HTTPStatus

import httpx

from mock_vws import MockVWS

_MODEL_TARGET_AUTHORIZATION = (
    "Bearer eyJhbGciOiJtb2NrIn0."
    "eyJzY29wZSI6Im1vZGVsdGFyZ2V0cy5zdGFuZGFyZG1vZGVsdGFyZ2V0LmFsbCJ9."
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


def test_standard_dataset_status() -> None:
    """``httpx`` requests can use Model Target Web API routes."""
    with MockVWS(processing_time_seconds=0):
        create_response = httpx.post(
            url="https://vws.vuforia.com/modeltargets/datasets",
            headers={"Authorization": _MODEL_TARGET_AUTHORIZATION},
            json=_MODEL_TARGET_DATASET_REQUEST,
            timeout=30,
        )
        dataset_uuid: object = create_response.json()["uuid"]
        assert isinstance(dataset_uuid, str)
        status_response = httpx.get(
            url=(
                "https://vws.vuforia.com/modeltargets/datasets/"
                f"{dataset_uuid}/status"
            ),
            headers={"Authorization": _MODEL_TARGET_AUTHORIZATION},
            timeout=30,
        )

    assert create_response.status_code == HTTPStatus.CREATED
    assert status_response.json()["status"] == "done"
