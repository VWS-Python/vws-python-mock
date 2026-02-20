"""Tests for the usage of the mock Flask application."""

import email.utils
import io
import json
import time
import uuid
from collections.abc import Iterator
from http import HTTPStatus

import pytest
import requests
import responses
from PIL import Image
from requests_mock_flask import add_flask_app_to_mock
from vws import VWS, CloudRecoService

from mock_vws._flask_server.target_manager import TARGET_MANAGER_FLASK_APP
from mock_vws._flask_server.vwq import CLOUDRECO_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import CloudDatabase, VuMarkDatabase
from tests.mock_vws.utils.usage_test_helpers import (
    processing_time_seconds,
)

_EXAMPLE_URL_FOR_TARGET_MANAGER = "http://" + uuid.uuid4().hex + ".com"


@pytest.fixture(autouse=True)
def _(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Enable a mock service backed by the Flask applications."""
    with responses.RequestsMock(
        assert_all_requests_are_fired=False,
    ) as mock_obj:
        add_flask_app_to_mock(
            mock_obj=mock_obj,
            flask_app=VWS_FLASK_APP,
            base_url="https://vws.vuforia.com",
        )

        add_flask_app_to_mock(
            mock_obj=mock_obj,
            flask_app=CLOUDRECO_FLASK_APP,
            base_url="https://cloudreco.vuforia.com",
        )

        add_flask_app_to_mock(
            mock_obj=mock_obj,
            flask_app=TARGET_MANAGER_FLASK_APP,
            base_url=_EXAMPLE_URL_FOR_TARGET_MANAGER,
        )

        monkeypatch.setenv(
            name="TARGET_MANAGER_BASE_URL",
            value=_EXAMPLE_URL_FOR_TARGET_MANAGER,
        )

        yield


class TestProcessingTime:
    """Tests for the time taken to process targets in the mock."""

    # There is a race condition in this test type - if tests start to
    # fail, consider increasing the leeway.
    LEEWAY = 0.5

    def test_default(
        self,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """By default, targets in the mock takes 2 seconds to be processed."""
        database = CloudDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

        time_taken = processing_time_seconds(
            vuforia_database=database,
            image=image_file_failed_state,
        )

        expected = 2
        assert expected - self.LEEWAY < time_taken < expected + self.LEEWAY

    def test_custom(
        self,
        image_file_failed_state: io.BytesIO,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """It is possible to set a custom processing time."""
        seconds = 5.0
        monkeypatch.setenv(
            name="PROCESSING_TIME_SECONDS",
            value=str(object=seconds),
        )
        database = CloudDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

        time_taken = processing_time_seconds(
            vuforia_database=database,
            image=image_file_failed_state,
        )

        expected = seconds
        assert expected - self.LEEWAY < time_taken < expected + self.LEEWAY


class TestAddDatabase:
    """Tests for adding databases to the mock."""

    @staticmethod
    def test_duplicate_keys() -> None:
        """
        It is not possible to have multiple databases with matching
        keys.
        """
        database = CloudDatabase(
            server_access_key="1",
            server_secret_key="2",
            client_access_key="3",
            client_secret_key="4",
            database_name="5",
        )

        bad_server_access_key_db = CloudDatabase(server_access_key="1")
        bad_server_secret_key_db = CloudDatabase(server_secret_key="2")
        bad_client_access_key_db = CloudDatabase(client_access_key="3")
        bad_client_secret_key_db = CloudDatabase(client_secret_key="4")
        bad_database_name_db = CloudDatabase(database_name="5")

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

        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

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
                timeout=30,
            )

            assert response.status_code == HTTPStatus.CONFLICT
            assert response.text == expected_message

    @staticmethod
    def test_duplicate_vumark_keys() -> None:
        """
        It is not possible to have multiple databases with matching
        keys, including VuMark databases.
        """
        database = VuMarkDatabase(
            server_access_key="v1",
            server_secret_key="v2",
            database_name="v3",
        )

        bad_server_access_key_db = VuMarkDatabase(server_access_key="v1")
        bad_server_secret_key_db = VuMarkDatabase(server_secret_key="v2")
        bad_database_name_db = VuMarkDatabase(database_name="v3")

        server_access_key_conflict_error = (
            "All server access keys must be unique. "
            'There is already a database with the server access key "v1".'
        )
        server_secret_key_conflict_error = (
            "All server secret keys must be unique. "
            'There is already a database with the server secret key "v2".'
        )
        database_name_conflict_error = (
            "All names must be unique. "
            'There is already a database with the name "v3".'
        )

        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/vumark_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

        for bad_database, expected_message in (
            (bad_server_access_key_db, server_access_key_conflict_error),
            (bad_server_secret_key_db, server_secret_key_conflict_error),
            (bad_database_name_db, database_name_conflict_error),
        ):
            response = requests.post(
                url=databases_url,
                json=bad_database.to_dict(),
                timeout=30,
            )

            assert response.status_code == HTTPStatus.CONFLICT
            assert response.text == expected_message

    @staticmethod
    def test_give_no_details(high_quality_image: io.BytesIO) -> None:
        """It is possible to create a database without giving any data."""
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(url=databases_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.CREATED

        data = json.loads(s=response.text)

        assert data["targets"] == []
        assert data["state_name"] == "WORKING"
        assert "database_name" in data

        vws_client = VWS(
            server_access_key=data["server_access_key"],
            server_secret_key=data["server_secret_key"],
        )

        cloud_reco_client = CloudRecoService(
            client_access_key=data["client_access_key"],
            client_secret_key=data["client_secret_key"],
        )

        assert not vws_client.list_targets()
        assert not cloud_reco_client.query(image=high_quality_image)


class TestDeleteDatabase:
    """Tests for deleting databases from the mock."""

    @staticmethod
    def test_not_found() -> None:
        """
        A 404 error is returned when trying to delete a database which
        does not
        exist.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        delete_url = databases_url + "/" + "foobar"
        response = requests.delete(url=delete_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.NOT_FOUND

    @staticmethod
    def test_delete_database() -> None:
        """It is possible to delete a database."""
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(url=databases_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.CREATED

        data = json.loads(s=response.text)
        delete_url = databases_url + "/" + data["database_name"]
        response = requests.delete(url=delete_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.OK

        response = requests.delete(url=delete_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.NOT_FOUND


class TestQueryImageMatchers:
    """Tests for query image matchers."""

    @staticmethod
    def test_exact_match(
        high_quality_image: io.BytesIO,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The exact matcher matches only exactly the same images."""
        monkeypatch.setenv(name="QUERY_IMAGE_MATCHER", value="exact")

        database = CloudDatabase()

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
        pil_image.save(fp=re_exported_image, format="PNG")

        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

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
    def test_structural_similarity_matcher(
        high_quality_image: io.BytesIO,
        different_high_quality_image: io.BytesIO,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The structural similarity matcher matches similar images."""
        monkeypatch.setenv(
            name="QUERY_IMAGE_MATCHER",
            value="structural_similarity",
        )
        database = CloudDatabase()
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
        pil_image.save(fp=re_exported_image, format="PNG")
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

        assert re_exported_image.getvalue() != high_quality_image.getvalue()

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
    def test_exact_match(
        high_quality_image: io.BytesIO,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The exact matcher matches only exactly the same images."""
        monkeypatch.setenv(name="DUPLICATES_IMAGE_MATCHER", value="exact")
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(fp=re_exported_image, format="PNG")

        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

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
    def test_structural_similarity_matcher(
        high_quality_image: io.BytesIO,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The structural similarity matcher matches similar images."""
        monkeypatch.setenv(
            name="DUPLICATES_IMAGE_MATCHER",
            value="structural_similarity",
        )
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(fp=re_exported_image, format="PNG")

        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

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


class TestTargetRaters:
    """Tests for using target raters."""

    @staticmethod
    def test_default(
        image_file_success_state_low_rating: io.BytesIO,
        high_quality_image: io.BytesIO,
    ) -> None:
        """By default, the BRISQUE target rater is used."""
        database = CloudDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        low_rating_image_target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_file_success_state_low_rating,
            application_metadata=None,
            active_flag=True,
        )

        high_quality_image_target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            application_metadata=None,
            active_flag=True,
        )

        for target_id in (
            low_rating_image_target_id,
            high_quality_image_target_id,
        ):
            vws_client.wait_for_target_processed(target_id=target_id)

        low_rated_image_rating = vws_client.get_target_record(
            target_id=low_rating_image_target_id,
        ).target_record.tracking_rating

        high_quality_image_rating = vws_client.get_target_record(
            target_id=high_quality_image_target_id,
        ).target_record.tracking_rating

        assert low_rated_image_rating <= 0
        assert high_quality_image_rating > 1

    @staticmethod
    def test_brisque(
        monkeypatch: pytest.MonkeyPatch,
        image_file_success_state_low_rating: io.BytesIO,
        high_quality_image: io.BytesIO,
    ) -> None:
        """It is possible to use the BRISQUE target rater."""
        monkeypatch.setenv(name="TARGET_RATER", value="brisque")

        database = CloudDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        low_rating_image_target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_file_success_state_low_rating,
            application_metadata=None,
            active_flag=True,
        )

        high_quality_image_target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            application_metadata=None,
            active_flag=True,
        )

        for target_id in (
            low_rating_image_target_id,
            high_quality_image_target_id,
        ):
            vws_client.wait_for_target_processed(target_id=target_id)

        low_rated_image_rating = vws_client.get_target_record(
            target_id=low_rating_image_target_id,
        ).target_record.tracking_rating

        high_quality_image_rating = vws_client.get_target_record(
            target_id=high_quality_image_target_id,
        ).target_record.tracking_rating

        assert low_rated_image_rating <= 0
        assert high_quality_image_rating > 1

    @staticmethod
    def test_perfect(
        monkeypatch: pytest.MonkeyPatch,
        high_quality_image: io.BytesIO,
    ) -> None:
        """It is possible to use the perfect target rater."""
        monkeypatch.setenv(name="TARGET_RATER", value="perfect")
        database = CloudDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        target_ids = [
            vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            for _ in range(50)
        ]

        for target_id in target_ids:
            vws_client.wait_for_target_processed(target_id=target_id)

        ratings_set = {
            vws_client.get_target_record(
                target_id=target_id
            ).target_record.tracking_rating
            for target_id in target_ids
        }

        assert ratings_set == {5}

    @staticmethod
    def test_random(
        monkeypatch: pytest.MonkeyPatch,
        high_quality_image: io.BytesIO,
    ) -> None:
        """It is possible to use the random target rater."""
        monkeypatch.setenv(name="TARGET_RATER", value="random")

        database = CloudDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        target_ids = [
            vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            for _ in range(50)
        ]

        for target_id in target_ids:
            vws_client.wait_for_target_processed(target_id=target_id)

        ratings = [
            vws_client.get_target_record(
                target_id=target_id
            ).target_record.tracking_rating
            for target_id in target_ids
        ]

        sorted_ratings = sorted(ratings)
        lowest_rating = sorted_ratings[0]
        highest_rating = sorted_ratings[-1]
        minimum_rating = 0
        maximum_rating = 5
        assert lowest_rating >= minimum_rating
        assert highest_rating <= maximum_rating
        assert lowest_rating != highest_rating


class TestResponseDelay:
    """Tests for the response delay feature.

    These tests run through the ``responses`` library, which intercepts
    requests in-process. Because of this, the client ``timeout`` parameter
    is not enforced — the delay blocks but never raises
    ``requests.exceptions.Timeout``. When running the Flask app as a real
    server (e.g. in Docker), the delay causes a genuinely slow HTTP
    response and the ``requests`` client will raise ``Timeout`` on its own.
    """

    DELAY_SECONDS = 0.5

    @staticmethod
    def _make_request() -> None:
        """Make a request to the VWS API."""
        requests.get(
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": email.utils.formatdate(
                    timeval=None,
                    localtime=False,
                    usegmt=True,
                ),
                "Authorization": "bad_auth_token",
            },
            data=b"",
            timeout=30,
        )

    def test_default_no_delay(self) -> None:
        """By default, there is no response delay."""
        database = CloudDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

        start = time.monotonic()
        self._make_request()
        elapsed = time.monotonic() - start
        assert elapsed < self.DELAY_SECONDS

    def test_delay_is_applied(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When response_delay_seconds is set, the response is delayed."""
        monkeypatch.setenv(
            name="RESPONSE_DELAY_SECONDS",
            value=f"{self.DELAY_SECONDS}",
        )
        database = CloudDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

        start = time.monotonic()
        self._make_request()
        elapsed = time.monotonic() - start
        assert elapsed >= self.DELAY_SECONDS
