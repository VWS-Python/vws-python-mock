"""
Tests for the usage of the mock for ``requests``.
"""

import email.utils
import io
import json
import socket
from datetime import datetime

import pytest
import requests
from freezegun import freeze_time
from requests.exceptions import MissingSchema
from requests_mock.exceptions import NoMockAddress
from vws import VWS
from vws_auth_tools import rfc_1123_date

from mock_vws import MockVWS
from mock_vws.database import VuforiaDatabase
from mock_vws.states import States
from mock_vws.target import Target
from tests.mock_vws.utils.usage_test_helpers import (
    process_deletion_seconds,
    processing_time_seconds,
    recognize_deletion_seconds,
)


def request_unmocked_address() -> None:
    """
    Make a request, using `requests` to an unmocked, free local address.

    Raises:
        requests.exceptions.ConnectionError: This is expected as there is
            nothing to connect to.
        requests_mock.exceptions.NoMockAddress: This request is being made in
            the context of a `requests_mock` mock which does not mock local
            addresses.
    """
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    address = f'http://localhost:{port}'
    requests.get(address)


def request_mocked_address() -> None:
    """
    Make a request, using `requests` to an address that is mocked by `MockVWS`.
    """
    requests.get(
        url='https://vws.vuforia.com/summary',
        headers={
            'Date': rfc_1123_date(),
            'Authorization': 'bad_auth_token',
        },
        data=b'',
    )


class TestRealHTTP:
    """
    Tests for making requests to mocked and unmocked addresses.
    """

    def test_default(self) -> None:
        """
        By default, the mock stops any requests made with `requests` to
        non-Vuforia addresses, but not to mocked Vuforia endpoints.
        """
        with MockVWS():
            with pytest.raises(NoMockAddress):
                request_unmocked_address()

            # No exception is raised when making a request to a mocked
            # endpoint.
            request_mocked_address()

        # The mocking stops when the context manager stops.
        with pytest.raises(requests.exceptions.ConnectionError):
            request_unmocked_address()

    def test_real_http(self) -> None:
        """
        When the `real_http` parameter given to the context manager is set to
        `True`, requests made to unmocked addresses are not stopped.
        """
        with MockVWS(real_http=True):
            with pytest.raises(requests.exceptions.ConnectionError):
                request_unmocked_address()


class TestProcessingTime:
    """
    Tests for the time taken to process targets in the mock.
    """

    # There is a race condition in this test type - if tests start to
    # fail, consider increasing the leeway.
    LEEWAY = 0.1

    def test_default(self, image_file_failed_state: io.BytesIO) -> None:
        """
        By default, targets in the mock take 0.5 seconds to be processed.
        """
        database = VuforiaDatabase()
        with MockVWS() as mock:
            mock.add_database(database=database)
            time_taken = processing_time_seconds(
                vuforia_database=database,
                image=image_file_failed_state,
            )

        expected = 0.5
        assert abs(expected - time_taken) < self.LEEWAY

    def test_custom(self, image_file_failed_state: io.BytesIO) -> None:
        """
        It is possible to set a custom processing time.
        """
        database = VuforiaDatabase()
        with MockVWS(processing_time_seconds=0.1) as mock:
            mock.add_database(database=database)
            time_taken = processing_time_seconds(
                vuforia_database=database,
                image=image_file_failed_state,
            )

        expected = 0.1
        assert abs(expected - time_taken) < self.LEEWAY


class TestDatabaseName:
    """
    Tests for the database name.
    """

    def test_default(self) -> None:
        """
        By default, the database has a random name.
        """
        database_details = VuforiaDatabase()
        other_database_details = VuforiaDatabase()
        assert (
            database_details.database_name
            != other_database_details.database_name
        )

    def test_custom_name(self) -> None:
        """
        It is possible to set a custom database name.
        """
        database_details = VuforiaDatabase(database_name='foo')
        assert database_details.database_name == 'foo'


class TestCustomBaseURLs:
    """
    Tests for using custom base URLs.
    """

    def test_custom_base_vws_url(self) -> None:
        """
        It is possible to use a custom base VWS URL.
        """
        with MockVWS(
            base_vws_url='https://vuforia.vws.example.com',
            real_http=False,
        ):
            with pytest.raises(NoMockAddress):
                requests.get('https://vws.vuforia.com/summary')

            requests.get(url='https://vuforia.vws.example.com/summary')
            requests.post('https://cloudreco.vuforia.com/v1/query')

    def test_custom_base_vwq_url(self) -> None:
        """
        It is possible to use a custom base cloud recognition URL.
        """
        with MockVWS(
            base_vwq_url='https://vuforia.vwq.example.com',
            real_http=False,
        ):
            with pytest.raises(NoMockAddress):
                requests.post('https://cloudreco.vuforia.com/v1/query')

            requests.post(url='https://vuforia.vwq.example.com/v1/query')
            requests.get('https://vws.vuforia.com/summary')

    def test_no_scheme(self) -> None:
        """
        An error if raised if a URL is given with no scheme.
        """
        with pytest.raises(MissingSchema) as exc:
            MockVWS(base_vws_url='vuforia.vws.example.com')

        expected = (
            'Invalid URL "vuforia.vws.example.com": No scheme supplied. '
            'Perhaps you meant "https://vuforia.vws.example.com".'
        )
        assert str(exc.value) == expected
        with pytest.raises(MissingSchema) as exc:
            MockVWS(base_vwq_url='vuforia.vwq.example.com')
        expected = (
            'Invalid URL "vuforia.vwq.example.com": No scheme supplied. '
            'Perhaps you meant "https://vuforia.vwq.example.com".'
        )
        assert str(exc.value) == expected


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
        with MockVWS() as mock:
            mock.add_database(database=database)
            time_taken = recognize_deletion_seconds(
                high_quality_image=high_quality_image,
                vuforia_database=database,
            )

        expected = 0.2
        assert abs(expected - time_taken) < self.LEEWAY

    def test_with_no_processing_time(
        self,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        This exercises some otherwise untouched code.
        """
        database = VuforiaDatabase()
        with MockVWS(query_processes_deletion_seconds=0) as mock:
            mock.add_database(database=database)
            time_taken = recognize_deletion_seconds(
                high_quality_image=high_quality_image,
                vuforia_database=database,
            )

        expected = 0.2
        assert abs(expected - time_taken) < self.LEEWAY

    def test_custom(
        self,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        It is possible to use set a custom amount of time that it takes for the
        Query API on the mock to recognize that a target has been deleted.
        """
        # We choose a low time for a quick test.
        query_recognizes_deletion = 0.5
        database = VuforiaDatabase()
        with MockVWS(
            query_recognizes_deletion_seconds=query_recognizes_deletion,
        ) as mock:
            mock.add_database(database=database)
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
        with MockVWS() as mock:
            mock.add_database(database=database)
            time_taken = process_deletion_seconds(
                high_quality_image=high_quality_image,
                vuforia_database=database,
            )

        expected = 3
        assert abs(expected - time_taken) < self.LEEWAY

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
            time_taken = process_deletion_seconds(
                high_quality_image=high_quality_image,
                vuforia_database=database,
            )

        expected = query_processes_deletion
        assert abs(expected - time_taken) < self.LEEWAY


class TestStates:
    """
    Tests for different mock states.
    """

    def test_repr(self) -> None:
        """
        The representation of a ``State`` shows the state.
        """
        assert repr(States.WORKING) == '<States.WORKING>'


class TestTargets:
    """
    Tests for target representations.
    """

    def test_to_dict(self, high_quality_image: io.BytesIO) -> None:
        """
        It is possible to dump a target to a dictionary and load it back.
        """
        database = VuforiaDatabase()

        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with MockVWS() as mock:
            mock.add_database(database=database)
            vws_client.add_target(
                name='example',
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )

        (target,) = database.targets
        target_dict = target.to_dict()

        # The dictionary is JSON dump-able
        assert json.dumps(target_dict)

        new_target = Target.from_dict(target_dict=target_dict)
        assert new_target == target

    def test_to_dict_deleted(self, high_quality_image: io.BytesIO) -> None:
        """
        It is possible to dump a deleted target to a dictionary and load it
        back.
        """
        database = VuforiaDatabase()

        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with MockVWS() as mock:
            mock.add_database(database=database)
            target_id = vws_client.add_target(
                name='example',
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            vws_client.delete_target(target_id=target_id)

        (target,) = database.targets
        target_dict = target.to_dict()

        # The dictionary is JSON dump-able
        assert json.dumps(target_dict)

        new_target = Target.from_dict(target_dict=target_dict)
        assert new_target.delete_date == target.delete_date


class TestDatabaseToDict:
    """
    Tests for dumping a database to a dictionary.
    """

    def test_to_dict(self, high_quality_image: io.BytesIO) -> None:
        """
        It is possible to dump a database to a dictionary and load it back.
        """
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        # We test a database with a target added.
        with MockVWS() as mock:
            mock.add_database(database=database)
            vws_client.add_target(
                name='example',
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )

        database_dict = database.to_dict()
        # The dictionary is JSON dump-able
        assert json.dumps(database_dict)

        new_database = VuforiaDatabase.from_dict(database_dict=database_dict)
        assert new_database == database


class TestDateHeader:
    """
    Tests for the date header in responses from mock routes.
    """

    def test_date_changes(self) -> None:
        """
        The date that the response is sent is in the response Date header.
        """
        new_year = 2012
        new_time = datetime(new_year, 1, 1)
        with MockVWS():
            with freeze_time(new_time):
                response = requests.get('https://vws.vuforia.com/summary')

        date_response = response.headers['Date']
        date_from_response = email.utils.parsedate(date_response)
        assert date_from_response is not None
        year = date_from_response[0]
        assert year == new_year


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

        with MockVWS() as mock:
            mock.add_database(database=database)
            for bad_database, expected_message in (
                (bad_server_access_key_db, server_access_key_conflict_error),
                (bad_server_secret_key_db, server_secret_key_conflict_error),
                (bad_client_access_key_db, client_access_key_conflict_error),
                (bad_client_secret_key_db, client_secret_key_conflict_error),
                (bad_database_name_db, database_name_conflict_error),
            ):
                with pytest.raises(ValueError) as exc:
                    mock.add_database(database=bad_database)

                assert str(exc.value) == expected_message
