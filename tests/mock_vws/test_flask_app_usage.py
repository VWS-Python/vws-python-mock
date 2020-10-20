"""
Tests for the usage of the mock Flask application.
"""

from mock_vws._flask_server.target_manager import TARGET_MANAGER_FLASK_APP
from mock_vws._flask_server.vwq import CLOUDRECO_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
import requests
import requests_mock
from requests_mock_flask import add_flask_app_to_mock
import io
import email.utils
import io
import json
import socket
from datetime import datetime, timedelta

import pytest
import requests
from freezegun import freeze_time
from requests.exceptions import MissingSchema
from requests_mock.exceptions import NoMockAddress
from vws import VWS, CloudRecoService
from vws.exceptions.cloud_reco_exceptions import MatchProcessing
from vws.reports import TargetStatuses
from vws_auth_tools import rfc_1123_date

from mock_vws import MockVWS
from mock_vws.database import VuforiaDatabase
from mock_vws.states import States
from mock_vws.target import Target

class TestProcessingTime:
    """
    Tests for the time taken to process targets in the mock.
    """

    def test_default(self, image_file_failed_state: io.BytesIO) -> None:
        """
        By default, targets in the mock take 0.5 seconds to be processed.
        """
        target_manager_base_url = 'http://example.com'
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
            VWS_FLASK_APP.config['TARGET_MANAGER_BASE_URL'] = target_manager_base_url

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
        pass

    def test_give_no_details(self) -> None:
        # Random stuff
        pass

    def test_delete_database(self) -> None:
        # Add one
        # Delete
        # Add another one same
        pass
