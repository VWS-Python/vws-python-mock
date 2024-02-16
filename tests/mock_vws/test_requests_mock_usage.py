"""
Tests for the usage of the mock for ``requests``.
"""
from __future__ import annotations

import datetime
import email.utils
import io
import json
import socket

import pytest
import requests
from freezegun import freeze_time
from mock_vws import MockVWS
from mock_vws.database import VuforiaDatabase
from mock_vws.image_matchers import ExactMatcher, StructuralSimilarityMatcher
from mock_vws.target import Target
from PIL import Image
from requests.exceptions import MissingSchema
from requests_mock.exceptions import NoMockAddress
from vws import VWS, CloudRecoService
from vws_auth_tools import rfc_1123_date

from tests.mock_vws.utils.usage_test_helpers import (
    processing_time_seconds,
)


def _not_exact_matcher(
    first_image_content: bytes,
    second_image_content: bytes,
) -> bool:
    return first_image_content != second_image_content


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
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    address = f"http://localhost:{port}"
    requests.get(address, timeout=30)


def request_mocked_address() -> None:
    """
    Make a request, using `requests` to an address that is mocked by `MockVWS`.
    """
    requests.get(
        url="https://vws.vuforia.com/summary",
        headers={
            "Date": rfc_1123_date(),
            "Authorization": "bad_auth_token",
        },
        data=b"",
        timeout=30,
    )


class TestRealHTTP:
    """
    Tests for making requests to mocked and unmocked addresses.
    """

    @staticmethod
    def test_default() -> None:
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

    @staticmethod
    def test_real_http() -> None:
        """
        When the `real_http` parameter given to the context manager is set to
        `True`, requests made to unmocked addresses are not stopped.
        """
        with (
            MockVWS(real_http=True),
            pytest.raises(requests.exceptions.ConnectionError),
        ):
            request_unmocked_address()


class TestProcessingTime:
    """
    Tests for the time taken to process targets in the mock.
    """

    # There is a race condition in this test type - if tests start to
    # fail, consider increasing the leeway.
    LEEWAY = 0.5

    def test_default(self, image_file_failed_state: io.BytesIO) -> None:
        """
        By default, targets in the mock takes 2 seconds to be processed.
        """
        database = VuforiaDatabase()
        with MockVWS() as mock:
            mock.add_database(database=database)
            time_taken = processing_time_seconds(
                vuforia_database=database,
                image=image_file_failed_state,
            )

        expected = 2
        assert expected - self.LEEWAY < time_taken < expected + self.LEEWAY

    def test_custom(self, image_file_failed_state: io.BytesIO) -> None:
        """
        It is possible to set a custom processing time.
        """
        database = VuforiaDatabase()
        seconds = 5
        with MockVWS(processing_time_seconds=seconds) as mock:
            mock.add_database(database=database)
            time_taken = processing_time_seconds(
                vuforia_database=database,
                image=image_file_failed_state,
            )

        expected = seconds
        assert expected - self.LEEWAY < time_taken < expected + self.LEEWAY


class TestDatabaseName:
    """
    Tests for the database name.
    """

    @staticmethod
    def test_default() -> None:
        """
        By default, the database has a random name.
        """
        database_details = VuforiaDatabase()
        other_database_details = VuforiaDatabase()
        assert (
            database_details.database_name
            != other_database_details.database_name
        )

    @staticmethod
    def test_custom_name() -> None:
        """
        It is possible to set a custom database name.
        """
        database_details = VuforiaDatabase(database_name="foo")
        assert database_details.database_name == "foo"


class TestCustomBaseURLs:
    """
    Tests for using custom base URLs.
    """

    @staticmethod
    def test_custom_base_vws_url() -> None:
        """
        It is possible to use a custom base VWS URL.
        """
        with MockVWS(
            base_vws_url="https://vuforia.vws.example.com",
            real_http=False,
        ):
            with pytest.raises(NoMockAddress):
                requests.get(url="https://vws.vuforia.com/summary", timeout=30)

            requests.get(
                url="https://vuforia.vws.example.com/summary",
                timeout=30,
            )
            requests.post(
                url="https://cloudreco.vuforia.com/v1/query",
                timeout=30,
            )

    @staticmethod
    def test_custom_base_vwq_url() -> None:
        """
        It is possible to use a custom base cloud recognition URL.
        """
        with MockVWS(
            base_vwq_url="https://vuforia.vwq.example.com",
            real_http=False,
        ):
            with pytest.raises(NoMockAddress):
                requests.post(
                    url="https://cloudreco.vuforia.com/v1/query",
                    timeout=30,
                )

            requests.post(
                url="https://vuforia.vwq.example.com/v1/query",
                timeout=30,
            )
            requests.get(
                url="https://vws.vuforia.com/summary",
                timeout=30,
            )

    @staticmethod
    def test_no_scheme() -> None:
        """
        An error if raised if a URL is given with no scheme.
        """
        with pytest.raises(MissingSchema) as vws_exc:
            MockVWS(base_vws_url="vuforia.vws.example.com")

        expected = (
            'Invalid URL "vuforia.vws.example.com": No scheme supplied. '
            'Perhaps you meant "https://vuforia.vws.example.com".'
        )
        assert str(vws_exc.value) == expected
        with pytest.raises(MissingSchema) as vwq_exc:
            MockVWS(base_vwq_url="vuforia.vwq.example.com")
        expected = (
            'Invalid URL "vuforia.vwq.example.com": No scheme supplied. '
            'Perhaps you meant "https://vuforia.vwq.example.com".'
        )
        assert str(vwq_exc.value) == expected


class TestTargets:
    """
    Tests for target representations.
    """

    @staticmethod
    def test_to_dict(high_quality_image: io.BytesIO) -> None:
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
                name="example",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )

        assert len(database.targets) == 1
        target = next(iter(database.targets))
        target_dict = target.to_dict()

        # The dictionary is JSON dump-able
        assert json.dumps(target_dict)

        new_target = Target.from_dict(target_dict=target_dict)
        assert new_target == target

    @staticmethod
    def test_to_dict_deleted(high_quality_image: io.BytesIO) -> None:
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
                name="example",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            vws_client.delete_target(target_id=target_id)

        assert len(database.targets) == 1
        target = next(iter(database.targets))
        target_dict = target.to_dict()

        # The dictionary is JSON dump-able
        assert json.dumps(target_dict)

        new_target = Target.from_dict(target_dict=target_dict)
        assert new_target.delete_date == target.delete_date


class TestDatabaseToDict:
    """
    Tests for dumping a database to a dictionary.
    """

    @staticmethod
    def test_to_dict(high_quality_image: io.BytesIO) -> None:
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
                name="example",
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

    @staticmethod
    def test_date_changes() -> None:
        """
        The date that the response is sent is in the response Date header.
        """
        new_year = 2012
        new_time = datetime.datetime(new_year, 1, 1, tzinfo=datetime.UTC)
        with MockVWS(), freeze_time(new_time):
            response = requests.get(
                url="https://vws.vuforia.com/summary",
                timeout=30,
            )

        date_response = response.headers["Date"]
        date_from_response = email.utils.parsedate(date_response)
        assert date_from_response is not None
        year = date_from_response[0]
        assert year == new_year


class TestAddDatabase:
    """
    Tests for adding databases to the mock.
    """

    @staticmethod
    def test_duplicate_keys() -> None:
        """
        It is not possible to have multiple databases with matching keys.
        """
        database = VuforiaDatabase(
            server_access_key="1",
            server_secret_key="2",
            client_access_key="3",
            client_secret_key="4",
            database_name="5",
        )

        bad_server_access_key_db = VuforiaDatabase(server_access_key="1")
        bad_server_secret_key_db = VuforiaDatabase(server_secret_key="2")
        bad_client_access_key_db = VuforiaDatabase(client_access_key="3")
        bad_client_secret_key_db = VuforiaDatabase(client_secret_key="4")
        bad_database_name_db = VuforiaDatabase(database_name="5")

        server_access_key_conflict_error = (
            "All server access keys must be unique. "
            'There is already a database with the server access key "1".'
        )
        server_secret_key_conflict_error = (
            "All server secret keys must be unique. "
            'There is already a database with the server secret key "2".'
        )
        client_access_key_conflict_error = (
            "All client access keys must be unique. "
            'There is already a database with the client access key "3".'
        )
        client_secret_key_conflict_error = (
            "All client secret keys must be unique. "
            'There is already a database with the client secret key "4".'
        )
        database_name_conflict_error = (
            "All names must be unique. "
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
                with pytest.raises(
                    ValueError,
                    match=expected_message + "$",
                ):
                    mock.add_database(database=bad_database)


class TestQueryImageMatchers:
    """Tests for query image matchers."""

    @staticmethod
    def test_exact_match(high_quality_image: io.BytesIO) -> None:
        """The exact matcher matches only exactly the same images."""
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        cloud_reco_client = CloudRecoService(
            client_access_key=database.client_access_key,
            client_secret_key=database.client_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(re_exported_image, format="PNG")

        with MockVWS(query_match_checker=ExactMatcher()) as mock:
            mock.add_database(database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            same_image_result = cloud_reco_client.query(
                image=high_quality_image,
            )
            assert len(same_image_result) == 1
            different_image_result = cloud_reco_client.query(
                image=re_exported_image,
            )
            assert not different_image_result

    @staticmethod
    def test_custom_matcher(high_quality_image: io.BytesIO) -> None:
        """It is possible to use a custom matcher."""
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        cloud_reco_client = CloudRecoService(
            client_access_key=database.client_access_key,
            client_secret_key=database.client_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(re_exported_image, format="PNG")

        with MockVWS(query_match_checker=_not_exact_matcher) as mock:
            mock.add_database(database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            same_image_result = cloud_reco_client.query(
                image=high_quality_image,
            )
            assert not same_image_result
            different_image_result = cloud_reco_client.query(
                image=re_exported_image,
            )
            assert len(different_image_result) == 1

    @staticmethod
    def test_structural_similarity_matcher(
        high_quality_image: io.BytesIO,
        different_high_quality_image: io.BytesIO,
    ) -> None:
        """The structural similarity matcher matches similar images."""
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        cloud_reco_client = CloudRecoService(
            client_access_key=database.client_access_key,
            client_secret_key=database.client_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(re_exported_image, format="PNG")

        with MockVWS(
            query_match_checker=StructuralSimilarityMatcher(),
        ) as mock:
            mock.add_database(database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            same_image_result = cloud_reco_client.query(
                image=high_quality_image,
            )
            assert len(same_image_result) == 1
            similar_image_result = cloud_reco_client.query(
                image=re_exported_image,
            )
            assert len(similar_image_result) == 1

            different_image_result = cloud_reco_client.query(
                image=different_high_quality_image,
            )
            assert not different_image_result


class TestDuplicatesImageMatchers:
    """Tests for duplicates image matchers."""

    @staticmethod
    def test_exact_match(high_quality_image: io.BytesIO) -> None:
        """The exact matcher matches only exactly the same images."""
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(re_exported_image, format="PNG")

        with MockVWS(duplicate_match_checker=ExactMatcher()) as mock:
            mock.add_database(database=database)
            target_id = vws_client.add_target(
                name="example_0",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            duplicate_target_id = vws_client.add_target(
                name="example_1",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            not_duplicate_target_id = vws_client.add_target(
                name="example_2",
                width=1,
                image=re_exported_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            vws_client.wait_for_target_processed(target_id=duplicate_target_id)
            vws_client.wait_for_target_processed(
                target_id=not_duplicate_target_id,
            )
            duplicates = vws_client.get_duplicate_targets(target_id=target_id)
            assert duplicates == [duplicate_target_id]

    @staticmethod
    def test_custom_matcher(high_quality_image: io.BytesIO) -> None:
        """It is possible to use a custom matcher."""
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(re_exported_image, format="PNG")

        with MockVWS(duplicate_match_checker=_not_exact_matcher) as mock:
            mock.add_database(database=database)
            target_id = vws_client.add_target(
                name="example_0",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            duplicate_target_id = vws_client.add_target(
                name="example_1",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            not_duplicate_target_id = vws_client.add_target(
                name="example_2",
                width=1,
                image=re_exported_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            vws_client.wait_for_target_processed(target_id=duplicate_target_id)
            vws_client.wait_for_target_processed(
                target_id=not_duplicate_target_id,
            )
            duplicates = vws_client.get_duplicate_targets(target_id=target_id)
            assert duplicates == [not_duplicate_target_id]

    @staticmethod
    def test_structural_similarity_matcher(
        high_quality_image: io.BytesIO,
    ) -> None:
        """The structural similarity matcher matches similar images."""
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(re_exported_image, format="PNG")

        with MockVWS(
            duplicate_match_checker=StructuralSimilarityMatcher(),
        ) as mock:
            mock.add_database(database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            duplicate_target_id = vws_client.add_target(
                name="example_1",
                width=1,
                image=re_exported_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            vws_client.wait_for_target_processed(target_id=duplicate_target_id)
            duplicates = vws_client.get_duplicate_targets(target_id=target_id)
            assert duplicates == [duplicate_target_id]
