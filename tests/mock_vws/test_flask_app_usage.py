"""
Tests for the usage of the mock Flask application.
"""

import io
from datetime import datetime, timedelta

import requests
import requests_mock
from _pytest.monkeypatch import MonkeyPatch
from requests_mock_flask import add_flask_app_to_mock
from vws import VWS
from vws.reports import TargetStatuses

from mock_vws._flask_server.target_manager import TARGET_MANAGER_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import VuforiaDatabase


class TestProcessingTime:
    """
    Tests for the time taken to process targets in the mock.
    """

    def test_default(
        self,
        image_file_failed_state: io.BytesIO,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """
        By default, targets in the mock take 0.5 seconds to be processed.
        """
        target_manager_base_url = 'http://example.com'
        monkeypatch.setenv(
            name='TARGET_MANAGER_BASE_URL',
            value=target_manager_base_url,
        )
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
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
    ) -> None:
        """
        It is possible to set a custom processing time.
        """
        target_manager_base_url = 'http://example.com'
        monkeypatch.setenv(
            name='TARGET_MANAGER_BASE_URL',
            value=target_manager_base_url,
        )
        monkeypatch.setenv(
            name='PROCESSING_TIME_SECONDS',
            value='0.1',
        )
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
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

            requests.post(url=target_manager_base_url + '/databases', json=database.to_dict())
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
