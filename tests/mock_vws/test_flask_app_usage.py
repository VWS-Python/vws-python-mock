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

from mock_vws._flask_server.target_manager import TARGET_MANAGER_FLASK_APP
from mock_vws._flask_server.vwq import CLOUDRECO_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils.usage_test_helpers import (
    processing_time_seconds,
    recognize_deletion_seconds,
    process_deletion_seconds,
)

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
        flask_app=CLOUDRECO_FLASK_APP,
        base_url='https://cloudreco.vuforia.com',
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
    ) -> None:
        """
        By default, targets in the mock take 0.5 seconds to be processed.
        """
        database = VuforiaDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + '/databases'
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


class TestCustomQueryRecognizesDeletionSeconds:
    """
    Tests for setting the amount of time after a target has been deleted
    until it is not recognized by the query endpoint.
    """

    LEEWAY = 0.15

    def test_default(
        self,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        By default it takes zero seconds for the Query API on the mock to
        recognize that a target has been deleted.

        The real Query API takes between zero and two seconds.
        See ``test_query`` for more information.
        """
        database = VuforiaDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + '/databases'
        requests.post(url=databases_url, json=database.to_dict())
        time_taken = recognize_deletion_seconds(
            high_quality_image=high_quality_image,
            vuforia_database=database,
        )

        expected = 0.2
        assert abs(expected - time_taken) < self.LEEWAY

    def test_custom(
        self,
        high_quality_image: io.BytesIO,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """
        It is possible to use set a custom amount of time that it takes for the
        Query API on the mock to recognize that a target has been deleted.
        """
        # We choose a low time for a quick test.
        query_recognizes_deletion = 0.5
        database = VuforiaDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + '/databases'
        requests.post(url=databases_url, json=database.to_dict())
        monkeypatch.setenv(
            name='DELETION_RECOGNITION_SECONDS',
            value=str(query_recognizes_deletion),
        )
        time_taken = recognize_deletion_seconds(
            high_quality_image=high_quality_image,
            vuforia_database=database,
        )

        expected = query_recognizes_deletion
        assert abs(expected - time_taken) < self.LEEWAY


class TestCustomQueryProcessDeletionSeconds:
    """
    Tests for setting the amount of time after a target has been deleted
    until it is not processed by the query endpoint.
    """

    def test_default(
        self,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        By default it takes three seconds for the Query API on the mock to
        process that a target has been deleted.

        The real Query API takes between seven and thirty seconds.
        See ``test_query`` for more information.
        """
        database = VuforiaDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + '/databases'
        requests.post(url=databases_url, json=database.to_dict())
        time_taken = process_deletion_seconds(
            high_quality_image=high_quality_image,
            vuforia_database=database,
        )

        expected = 3
        assert abs(expected - time_taken) < 0.1

    def test_custom(
        self,
        high_quality_image: io.BytesIO,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """
        It is possible to use set a custom amount of time that it takes for the
        Query API on the mock to process that a target has been deleted.
        """
        # We choose a low time for a quick test.
        query_processes_deletion = 0.1
        database = VuforiaDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + '/databases'
        requests.post(url=databases_url, json=database.to_dict())
        monkeypatch.setenv(
            name='DELETION_PROCESSING_SECONDS',
            value=str(query_processes_deletion),
        )
        time_taken = process_deletion_seconds(
            high_quality_image=high_quality_image,
            vuforia_database=database,
        )

        expected = query_processes_deletion
        assert abs(expected - time_taken) < 0.1


class TestDatabaseManagement:
    """
    TODO
    """

    def test_duplicate_keys(self) -> None:
        """
        It is not possible to have multiple databases with matching keys.
        """
        # Add one
        # Add another different
        # Add another conflict

    def test_give_no_details(self) -> None:
        # Random stuff
        pass

    def test_delete_database(self) -> None:
        # Add one
        # Delete
        # Add another one same
        pass
