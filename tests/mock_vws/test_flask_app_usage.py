"""
Tests for the usage of the mock Flask application.
"""

import io
import uuid
from http import HTTPStatus

import pytest
import requests
from pytest import MonkeyPatch
from requests_mock import Mocker
from requests_mock_flask import add_flask_app_to_mock
from vws import VWS, CloudRecoService

from mock_vws._flask_server.target_manager import TARGET_MANAGER_FLASK_APP
from mock_vws._flask_server.vwq import CLOUDRECO_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils.usage_test_helpers import (
    process_deletion_seconds,
    processing_time_seconds,
    recognize_deletion_seconds,
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
    LEEWAY = 0.1

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

    # There is a race condition in this test type - if tests start to
    # fail, consider increasing the leeway.
    LEEWAY = 0.2

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
        assert abs(expected - time_taken) < self.LEEWAY

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
        assert abs(expected - time_taken) < self.LEEWAY


class TestAddDatabase:
    """
    Tests for adding databases to the mock.
    """

    def test_duplicate_keys(self) -> None:
        """
        It is not possible to have multiple databases with matching keys.
        """
        database = VuforiaDatabase(
            server_access_key='1',
            server_secret_key='2',
            client_access_key='3',
            client_secret_key='4',
            database_name='5',
        )

        bad_server_access_key_db = VuforiaDatabase(server_access_key='1')
        bad_server_secret_key_db = VuforiaDatabase(server_secret_key='2')
        bad_client_access_key_db = VuforiaDatabase(client_access_key='3')
        bad_client_secret_key_db = VuforiaDatabase(client_secret_key='4')
        bad_database_name_db = VuforiaDatabase(database_name='5')

        server_access_key_conflict_error = (
            'All server access keys must be unique. '
            'There is already a database with the server access key "1".'
        )
        server_secret_key_conflict_error = (
            'All server secret keys must be unique. '
            'There is already a database with the server secret key "2".'
        )
        client_access_key_conflict_error = (
            'All client access keys must be unique. '
            'There is already a database with the client access key "3".'
        )
        client_secret_key_conflict_error = (
            'All client secret keys must be unique. '
            'There is already a database with the client secret key "4".'
        )
        database_name_conflict_error = (
            'All names must be unique. '
            'There is already a database with the name "5".'
        )

        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + '/databases'
        requests.post(url=databases_url, json=database.to_dict())

        for bad_database, expected_message in (
            (bad_server_access_key_db, server_access_key_conflict_error),
            (bad_server_secret_key_db, server_secret_key_conflict_error),
            (bad_client_access_key_db, client_access_key_conflict_error),
            (bad_client_secret_key_db, client_secret_key_conflict_error),
            (bad_database_name_db, database_name_conflict_error),
        ):
            response = requests.post(
                url=databases_url,
                json=bad_database.to_dict(),
            )

            assert response.status_code == HTTPStatus.CONFLICT
            assert response.text == expected_message

    def test_give_no_details(self, high_quality_image: io.BytesIO) -> None:
        """
        It is possible to create a database without giving any data.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + '/databases'
        response = requests.post(url=databases_url, json={})
        assert response.status_code == HTTPStatus.CREATED

        data = response.json()

        assert data['targets'] == []
        assert data['state_name'] == 'WORKING'
        assert 'database_name' in data.keys()

        vws_client = VWS(
            server_access_key=data['server_access_key'],
            server_secret_key=data['server_secret_key'],
        )

        cloud_reco_client = CloudRecoService(
            client_access_key=data['client_access_key'],
            client_secret_key=data['client_secret_key'],
        )

        assert not vws_client.list_targets()
        assert not cloud_reco_client.query(image=high_quality_image)


class TestDeleteDatabase:
    """
    Tests for deleting databases from the mock.
    """

    def test_not_found(self) -> None:
        """
        A 404 error is returned when trying to delete a database which does not
        exist.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + '/databases'
        delete_url = databases_url + '/' + 'foobar'
        response = requests.delete(url=delete_url, json={})
        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_delete_database(self) -> None:
        """
        It is possible to delete a database.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + '/databases'
        response = requests.post(url=databases_url, json={})
        assert response.status_code == HTTPStatus.CREATED

        data = response.json()
        delete_url = databases_url + '/' + data['database_name']
        response = requests.delete(url=delete_url, json={})
        assert response.status_code == HTTPStatus.OK

        response = requests.delete(url=delete_url, json={})
        assert response.status_code == HTTPStatus.NOT_FOUND
