"""
Tests for the usage of the mock Flask application.
"""

import io
import uuid

import pytest
import requests
from _pytest.monkeypatch import MonkeyPatch
from requests_mock import Mocker
from requests_mock_flask import add_flask_app_to_mock
from vws import VWS

from mock_vws._flask_server.target_manager import TARGET_MANAGER_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils.usage_test_helpers import processing_time_seconds


_EXAMPLE_URL_FOR_TARGET_MANAGER = 'http://' + uuid.uuid4().hex + '.com'

@pytest.fixture(autouse=True)
def enable_requests_mock(
    monkeypatch: MonkeyPatch,
    requests_mock: Mocker,
) -> None:
    """
    Enable a mock service backed by the Flask applications.
    """
    add_flask_app_to_mock(
        mock_obj=requests_mock,
        flask_app=VWS_FLASK_APP,
        base_url='https://vws.vuforia.com',
    )

    add_flask_app_to_mock(
        mock_obj=requests_mock,
        flask_app=TARGET_MANAGER_FLASK_APP,
        base_url=_EXAMPLE_URL_FOR_TARGET_MANAGER,
    )

    monkeypatch.setenv(
        name='TARGET_MANAGER_BASE_URL',
        value=_EXAMPLE_URL_FOR_TARGET_MANAGER,
    )


class TestProcessingTime:
    """
    Tests for the time taken to process targets in the mock.
    """

    # There is a race condition in this test type - if tests start to
    # fail, consider increasing the leeway.
    LEEWAY = 0.05

    def test_default(
        self,
        image_file_failed_state: io.BytesIO,
        target_manager_base_url: str,
    ) -> None:
        """
        By default, targets in the mock take 0.5 seconds to be processed.
        """
        database = VuforiaDatabase()
        databases_url = target_manager_base_url + '/databases'
        requests.post(url=databases_url, json=database.to_dict())

        time_taken = processing_time_seconds(
            vuforia_database=database,
            image=image_file_failed_state,
        )

        expected = 0.5
        assert abs(expected - time_taken) < self.LEEWAY

    def test_custom(
        self,
        image_file_failed_state: io.BytesIO,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """
        It is possible to set a custom processing time.
        """
        monkeypatch.setenv(
            name='PROCESSING_TIME_SECONDS',
            value='0.1',
        )
        database = VuforiaDatabase()

        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + '/databases'
        requests.post(url=databases_url, json=database.to_dict())

        time_taken = processing_time_seconds(
            vuforia_database=database,
            image=image_file_failed_state,
        )

        expected = 0.1
        assert abs(expected - time_taken) < self.LEEWAY
