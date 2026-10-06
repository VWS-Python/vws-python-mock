"""Tests for processing through the Flask app."""

import io

import pytest
import requests

from mock_vws.database import CloudDatabase
from tests.mock_vws.utils.usage_test_helpers import (
    processing_time_seconds,
)


class TestProcessingTime:
    """Tests for the time taken to process targets in the mock."""

    # There is a race condition in this test type - if tests start to
    # fail, consider increasing the leeway.
    LEEWAY = 1.0

    def test_default(
        self, image_file_failed_state: io.BytesIO, target_manager_url: str
    ) -> None:
        """By default, targets in the mock takes 2 seconds to be processed."""
        database = CloudDatabase()
        databases_url = target_manager_url + "/cloud_databases"
        _ = requests.post(
            url=databases_url, json=database.to_dict(), timeout=30
        )

        time_taken = processing_time_seconds(
            vuforia_database=database,
            image=image_file_failed_state,
        )

        expected = 2
        assert expected - self.LEEWAY < time_taken < expected + self.LEEWAY

    def test_custom(
        self,
        *,
        image_file_failed_state: io.BytesIO,
        monkeypatch: pytest.MonkeyPatch,
        target_manager_url: str,
    ) -> None:
        """It is possible to set a custom processing time."""
        seconds = 5.0
        monkeypatch.setenv(
            name="PROCESSING_TIME_SECONDS",
            value=str(object=seconds),
        )
        database = CloudDatabase()
        databases_url = target_manager_url + "/cloud_databases"
        _ = requests.post(
            url=databases_url, json=database.to_dict(), timeout=30
        )

        time_taken = processing_time_seconds(
            vuforia_database=database,
            image=image_file_failed_state,
        )

        expected = seconds
        assert expected - self.LEEWAY < time_taken < expected + self.LEEWAY
