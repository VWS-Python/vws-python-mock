"""
Tests for the usage of the mock Flask application.
"""
from __future__ import annotations

import io
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
import requests
from mock_vws._flask_server.target_manager import TARGET_MANAGER_FLASK_APP
from mock_vws._flask_server.vwq import CLOUDRECO_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import VuforiaDatabase
from PIL import Image
from requests_mock_flask import add_flask_app_to_mock
from vws import VWS, CloudRecoService

from tests.mock_vws.utils.usage_test_helpers import (
    processing_time_seconds,
)

if TYPE_CHECKING:
    from requests_mock import Mocker

_EXAMPLE_URL_FOR_TARGET_MANAGER = "http://" + uuid.uuid4().hex + ".com"


@pytest.fixture(autouse=True)
def _(monkeypatch: pytest.MonkeyPatch, requests_mock: Mocker) -> None:
    """
    Enable a mock service backed by the Flask applications.
    """
    add_flask_app_to_mock(
        mock_obj=requests_mock,
        flask_app=VWS_FLASK_APP,
        base_url="https://vws.vuforia.com",
    )

    add_flask_app_to_mock(
        mock_obj=requests_mock,
        flask_app=CLOUDRECO_FLASK_APP,
        base_url="https://cloudreco.vuforia.com",
    )

    add_flask_app_to_mock(
        mock_obj=requests_mock,
        flask_app=TARGET_MANAGER_FLASK_APP,
        base_url=_EXAMPLE_URL_FOR_TARGET_MANAGER,
    )

    monkeypatch.setenv(
        name="TARGET_MANAGER_BASE_URL",
        value=_EXAMPLE_URL_FOR_TARGET_MANAGER,
    )


class TestProcessingTime:
    """
    Tests for the time taken to process targets in the mock.
    """

    # There is a race condition in this test type - if tests start to
    # fail, consider increasing the leeway.
    LEEWAY = 0.5

    def test_default(
        self,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        By default, targets in the mock takes 2 seconds to be processed.
        """
        database = VuforiaDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/databases"
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
        """
        It is possible to set a custom processing time.
        """
        seconds = 5
        monkeypatch.setenv(
            name="PROCESSING_TIME_SECONDS",
            value=str(seconds),
        )
        database = VuforiaDatabase()
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/databases"
        requests.post(url=databases_url, json=database.to_dict(), timeout=30)

        time_taken = processing_time_seconds(
            vuforia_database=database,
            image=image_file_failed_state,
        )

        expected = seconds
        assert expected - self.LEEWAY < time_taken < expected + self.LEEWAY


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

        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/databases"
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
    def test_give_no_details(high_quality_image: io.BytesIO) -> None:
        """
        It is possible to create a database without giving any data.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/databases"
        response = requests.post(url=databases_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.CREATED

        data = response.json()

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
    """
    Tests for deleting databases from the mock.
    """

    @staticmethod
    def test_not_found() -> None:
        """
        A 404 error is returned when trying to delete a database which does not
        exist.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/databases"
        delete_url = databases_url + "/" + "foobar"
        response = requests.delete(url=delete_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.NOT_FOUND

    @staticmethod
    def test_delete_database() -> None:
        """
        It is possible to delete a database.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/databases"
        response = requests.post(url=databases_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.CREATED

        data = response.json()
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

        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/databases"
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
            name="QUERY_IMAGE_MATCHER", value="structural_similarity"
        )
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
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/databases"
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
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(re_exported_image, format="PNG")

        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/databases"
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
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        pil_image = Image.open(fp=high_quality_image)
        re_exported_image = io.BytesIO()
        pil_image.save(re_exported_image, format="PNG")

        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/databases"
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
