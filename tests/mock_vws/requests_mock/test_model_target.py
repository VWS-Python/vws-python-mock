"""Tests for the core Model Target dataset model."""

import pytest

from mock_vws.model_target import ModelTargetDataset, ModelTargetDatasetType


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
