"""
Tests for the usage of the mock Flask application.
"""

import io
from datetime import datetime, timedelta
from typing import Generator
import uuid

import requests
import requests_mock
from _pytest.monkeypatch import MonkeyPatch
import pytest
from requests_mock_flask import add_flask_app_to_mock
from vws import VWS
from vws.reports import TargetStatuses

from mock_vws._flask_server.target_manager import TARGET_MANAGER_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import VuforiaDatabase


@pytest.fixture()
def target_manager_base_url() -> str:
    return 'http://' + uuid.uuid4().hex + '.com'

@pytest.fixture(autouse=True)
def enable_requests_mock(
    target_manager_base_url: str,
    monkeypatch: MonkeyPatch,
) -> Generator:
    with requests_mock.Mocker(real_http=False) as mock:
        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=VWS_FLASK_APP,
            base_url='https://vws.vuforia.com',
        )

        add_flask_app_to_mock(
            mock_obj=mock,
            flask_app=TARGET_MANAGER_FLASK_APP,
            base_url=target_manager_base_url,
        )

        monkeypatch.setenv(
            name='TARGET_MANAGER_BASE_URL',
            value=target_manager_base_url,
        )

        yield

class TestProcessingTime:
    """
    Tests for the time taken to process targets in the mock.
    """

    def test_default(
        self,
        image_file_failed_state: io.BytesIO,
        monkeypatch: MonkeyPatch,
        target_manager_base_url: str,
    ) -> None:
        """
        By default, targets in the mock take 0.5 seconds to be processed.
        """
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        databases_url = target_manager_base_url + '/databases'
        requests.post(url=databases_url, json=database.to_dict())

        target_id = vws_client.add_target(
            name='example',
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )
        start_time = datetime.now()

        while True:
            target_details = vws_client.get_target_record(
                target_id=target_id,
            )

            status = target_details.status
            if status != TargetStatuses.PROCESSING:
                elapsed_time = datetime.now() - start_time
                # There is a race condition in this test - if it starts to
                # fail, maybe extend the acceptable range.
                assert elapsed_time < timedelta(seconds=0.55)
                assert elapsed_time > timedelta(seconds=0.49)
                return

    def test_custom(
        self,
        image_file_failed_state: io.BytesIO,
        monkeypatch: MonkeyPatch,
        target_manager_base_url: str,
    ) -> None:
        """
        It is possible to set a custom processing time.
        """
        monkeypatch.setenv(
            name='PROCESSING_TIME_SECONDS',
            value='0.1',
        )
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        databases_url = target_manager_base_url + '/databases'
        requests.post(url=databases_url, json=database.to_dict())
        target_id = vws_client.add_target(
            name='example',
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )

        start_time = datetime.now()

        while True:
            target_details = vws_client.get_target_record(
                target_id=target_id,
            )

            status = target_details.status
            if status != TargetStatuses.PROCESSING:
                elapsed_time = datetime.now() - start_time
                assert elapsed_time < timedelta(seconds=0.15)
                assert elapsed_time > timedelta(seconds=0.09)
                return


class TestCustomQueryRecognizesDeletionSeconds:
    """
    Tests for setting the amount of time after a target has been deleted
    until it is not recognized by the query endpoint.
    """
    def _process_deletion_seconds(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> float:
        """
        The number of seconds it takes for the query endpoint to process a
        deletion.
        """
        _add_and_delete_target(
            image=high_quality_image,
            vuforia_database=vuforia_database,
        )

        _wait_for_deletion_recognized(
            image=high_quality_image,
            vuforia_database=vuforia_database,
        )

        time_after_deletion_recognized = datetime.now()

        _wait_for_deletion_processed(
            image=high_quality_image,
            vuforia_database=vuforia_database,
        )

        time_difference = datetime.now() - time_after_deletion_recognized
        return time_difference.total_seconds()

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
        with MockVWS() as mock:
            mock.add_database(database=database)
            process_deletion_seconds = self._process_deletion_seconds(
                high_quality_image=high_quality_image,
                vuforia_database=database,
            )

        expected = 3
        assert abs(expected - process_deletion_seconds) < 0.1

    def test_custom(
        self,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        It is possible to use set a custom amount of time that it takes for the
        Query API on the mock to process that a target has been deleted.
        """
        # We choose a low time for a quick test.
        query_processes_deletion = 0.1
        database = VuforiaDatabase()
        with MockVWS(
            query_processes_deletion_seconds=query_processes_deletion,
        ) as mock:
            mock.add_database(database=database)
            process_deletion_seconds = self._process_deletion_seconds(
                high_quality_image=high_quality_image,
                vuforia_database=database,
            )

        expected = query_processes_deletion
        assert abs(expected - process_deletion_seconds) < 0.1


class TestCustomQueryProcessDeletionSeconds:
    """
    Tests for setting the amount of time after a target has been deleted
    until it is not processed by the query endpoint.
    """


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
