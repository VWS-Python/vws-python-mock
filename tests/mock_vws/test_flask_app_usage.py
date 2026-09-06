"""Tests for the usage of the mock Flask application."""

import base64
import email.utils
import io
import json
import sys
import threading
import time
import uuid
import zipfile
from collections.abc import Callable, Iterator
from http import HTTPMethod, HTTPStatus
from typing import Any

import pytest
import requests
import responses
from PIL import Image
from requests_mock_flask import add_flask_app_to_mock
from vws import VWS, CloudRecoService
from vws.exceptions.vws_exceptions import (
    RequestQuotaReachedError,
    TargetQuotaReachedError,
    TooManyRequestsError,
)
from vws_auth_tools import authorization_header, rfc_1123_date
from werkzeug.serving import BaseWSGIServer, make_server

from mock_vws._constants import ResultCodes
from mock_vws._flask_server.target_manager import (
    TARGET_MANAGER,
    TARGET_MANAGER_FLASK_APP,
)
from mock_vws._flask_server.vwq import CLOUDRECO_FLASK_APP
from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.model_target import (
    ModelTargetDataset,
    ModelTargetDatasetType,
    ModelTargetGenerationFailure,
    ModelTargetGenerationWarning,
)
from mock_vws.request_rate_limits import RequestRateLimit, RequestRateLimits
from mock_vws.target import VuMarkTarget
from tests.mock_vws.utils.usage_test_helpers import (
    processing_time_seconds,
)

_EXAMPLE_URL_FOR_TARGET_MANAGER = "http://" + uuid.uuid4().hex + ".com"
_MODEL_TARGET_DATASET_REQUEST = {
    "name": "dataset-name",
    "targetSdk": "10.18",
    "models": [
        {
            "name": "model-name",
            "cadDataUrl": "https://example.com/model.glb",
            "views": [
                {
                    "name": "view-name",
                    "guideViewPosition": {
                        "translation": [0, 0, 5],
                        "rotation": [0, 0, 0, 1],
                    },
                },
            ],
        },
    ],
}


@pytest.fixture(autouse=True)
def _(*, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
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

        # Some tests serve an application themselves, on a local port, so
        # that they can make requests to it at the same time as each other.
        # Those requests are made for real rather than mocked.
        mock_obj.add_passthru(prefix="http://127.0.0.1")

        yield

    for cloud_database in TARGET_MANAGER.cloud_databases:
        TARGET_MANAGER.remove_cloud_database(cloud_database=cloud_database)
    for vumark_database in TARGET_MANAGER.vumark_databases:
        TARGET_MANAGER.remove_vumark_database(vumark_database=vumark_database)
    for dataset_uuid in TARGET_MANAGER.model_target_datasets:
        TARGET_MANAGER.remove_model_target_dataset(dataset_uuid=dataset_uuid)


class TestProcessingTime:
    """Tests for the time taken to process targets in the mock."""

    # There is a race condition in this test type - if tests start to
    # fail, consider increasing the leeway.
    LEEWAY = 1.0

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
        *,
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


class TestRequestQuota:
    """Tests for request quota exhaustion in the Flask mock."""

    @staticmethod
    def test_request_quota_reached() -> None:
        """The Flask mock preserves and enforces a zero request quota."""
        database = CloudDatabase(request_quota=0)
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(
            url=databases_url,
            json=database.to_dict(),
            timeout=30,
        )
        response.raise_for_status()
        client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with pytest.raises(expected_exception=RequestQuotaReachedError):
            client.list_targets()

    @staticmethod
    def test_target_quota_reached(
        *,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """The Flask mock preserves and enforces a zero target quota."""
        database = CloudDatabase(target_quota=0)
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(
            url=databases_url,
            json=database.to_dict(),
            timeout=30,
        )
        response.raise_for_status()
        client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with pytest.raises(expected_exception=TargetQuotaReachedError):
            client.add_target(
                name="example",
                width=1,
                image=image_file_failed_state,
                application_metadata=None,
                active_flag=True,
            )

    @staticmethod
    def test_too_many_requests() -> None:
        """The Flask mock preserves and enforces a zero request rate limit."""
        database = CloudDatabase(requests_per_second_limit=0)
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(
            url=databases_url,
            json=database.to_dict(),
            timeout=30,
        )
        response.raise_for_status()
        client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with pytest.raises(expected_exception=TooManyRequestsError):
            client.list_targets()

    @staticmethod
    def test_per_endpoint_limits() -> None:
        """The Flask mock preserves and enforces per-endpoint limits."""
        database = CloudDatabase(
            request_rate_limits=RequestRateLimits(
                list_targets=RequestRateLimit(
                    max_requests=1,
                    window_seconds=60.0,
                ),
            ),
        )
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(
            url=databases_url,
            json=database.to_dict(),
            timeout=30,
        )
        response.raise_for_status()
        client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        client.list_targets()
        with pytest.raises(expected_exception=TooManyRequestsError):
            client.list_targets()

        # Other endpoints are not limited.
        client.get_database_summary_report()


class TestRecognitionCounts:
    """Tests for recognition counts in the Flask mock.

    The in-memory mock uses the ``CloudDatabase`` object which it is given,
    so it shows whatever counts that object has. The Flask mock keeps its
    databases in the target manager service, so the counts have to survive
    the trip through it.
    """

    CURRENT_MONTH_RECOS = 3
    PREVIOUS_MONTH_RECOS = 5
    TOTAL_RECOS = 8
    RECO_THRESHOLD = 20

    def test_seeded_database_counts(self) -> None:
        """The Flask mock preserves the counts of a seeded database."""
        database = CloudDatabase(
            current_month_recos=self.CURRENT_MONTH_RECOS,
            previous_month_recos=self.PREVIOUS_MONTH_RECOS,
            total_recos=self.TOTAL_RECOS,
            reco_threshold=self.RECO_THRESHOLD,
        )
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(
            url=databases_url,
            json=database.to_dict(),
            timeout=30,
        )
        response.raise_for_status()
        client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        report = client.get_database_summary_report()

        assert report.current_month_recos == self.CURRENT_MONTH_RECOS
        assert report.previous_month_recos == self.PREVIOUS_MONTH_RECOS
        assert report.total_recos == self.TOTAL_RECOS
        assert report.reco_threshold == self.RECO_THRESHOLD


class TestUnroutedRequests:
    """Tests for requests which the Flask app does not route.

    Signed requests are covered by
    ``tests/mock_vws/test_invalid_given_id.py``, which verifies the
    responses against real Vuforia.
    """

    @staticmethod
    def test_unauthenticated_unknown_path() -> None:
        """A request to a path which is not routed returns a 404 even
        without credentials.

        The Docker health check relies on this request returning a
        response.
        """
        response = VWS_FLASK_APP.test_client().get("/some-random-endpoint")

        assert response.status_code == HTTPStatus.NOT_FOUND


class TestAddCloudDatabase:
    """Tests for adding cloud databases to the mock."""

    @staticmethod
    def test_duplicate_keys() -> None:
        """
        It is not possible to have multiple cloud databases with
        matching
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
    def test_give_no_details(high_quality_image: io.BytesIO) -> None:
        """It is possible to create a cloud database without giving any
        data.
        """
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

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("body", "expected_loc", "expected_message"),
        argvalues=[
            (
                {"state_name": "inactive"},
                ["state_name"],
                (
                    "Value error, Input should be one of 'WORKING', "
                    "'PROJECT_SUSPENDED', 'PROJECT_INACTIVE', "
                    "'PROJECT_HAS_NO_API_ACCESS'"
                ),
            ),
            (
                {"state_name": "project_inactive"},
                ["state_name"],
                (
                    "Value error, Input should be one of 'WORKING', "
                    "'PROJECT_SUSPENDED', 'PROJECT_INACTIVE', "
                    "'PROJECT_HAS_NO_API_ACCESS'"
                ),
            ),
            (
                {"database_type_name": "cloud"},
                ["database_type_name"],
                "Value error, Input should be one of 'CLOUD_RECO'",
            ),
            (
                {"request_quota": "100"},
                ["request_quota"],
                "Input should be a valid integer",
            ),
            (
                {"request_rate_limits": {"other": {"max_requests": 1}}},
                ["request_rate_limits", "other", "window_seconds"],
                "Field required",
            ),
            (
                {"request_rate_limits": [1, 2]},
                ["request_rate_limits"],
                (
                    "Input should be a valid dictionary or instance of "
                    "RequestRateLimitsBody"
                ),
            ),
        ],
        ids=[
            "unknown_state_name",
            "lowercase_state_name",
            "unknown_database_type_name",
            "request_quota_is_a_string",
            "request_rate_limit_missing_a_key",
            "request_rate_limits_wrong_type",
        ],
    )
    def test_invalid_field(
        body: dict[str, Any],
        expected_loc: list[str],
        expected_message: str,
    ) -> None:
        """A field with an unaccepted value gives a 400 response which
        names the field and describes what is accepted.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(url=databases_url, json=body, timeout=30)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.headers["Content-Type"] == "application/json"
        (error,) = response.json()["errors"]
        assert error["loc"] == expected_loc
        assert error["msg"] == expected_message
        assert not TARGET_MANAGER.cloud_databases

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("data", "expected_message"),
        argvalues=[
            ("not json", "Expecting value: line 1 column 1 (char 0)"),
            ("[]", "Input should be an object"),
        ],
        ids=["not_json", "not_an_object"],
    )
    def test_body_not_an_object(data: str, expected_message: str) -> None:
        """A body which is not a JSON object gives a 400 response."""
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(
            url=databases_url,
            data=data,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        (error,) = response.json()["errors"]
        assert error["type"] == "value_error"
        assert error["loc"] == []
        assert error["msg"] == expected_message

    @staticmethod
    def test_null_field() -> None:
        """A field which cannot be null is rejected when given as null, and
        a field which can be null is accepted.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(
            url=databases_url,
            json={"request_quota": None},
            timeout=30,
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        (error,) = response.json()["errors"]
        assert error["loc"] == ["request_quota"]
        assert error["msg"] == "Input should be a valid integer"

        response = requests.post(
            url=databases_url,
            json={"requests_per_second_limit": None},
            timeout=30,
        )

        assert response.status_code == HTTPStatus.CREATED
        assert response.json()["requests_per_second_limit"] is None

    @staticmethod
    def test_partial_request_rate_limits() -> None:
        """Groups of endpoints which are not given in the request rate
        limits have no limit of their own.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(
            url=databases_url,
            json={
                "request_rate_limits": {
                    "get_target": {"max_requests": 3, "window_seconds": 1},
                },
            },
            timeout=30,
        )

        assert response.status_code == HTTPStatus.CREATED
        assert response.json()["request_rate_limits"] == {
            "other": None,
            "get_target": {"max_requests": 3, "window_seconds": 1.0},
            "get_duplicates": None,
            "list_targets": None,
        }


class TestAddVuMarkDatabase:
    """Tests for adding VuMark databases to the mock."""

    @staticmethod
    def test_duplicate_keys() -> None:
        """
        It is not possible to have multiple VuMark databases with
        matching
        keys.
        """
        database = VuMarkDatabase(
            server_access_key="1",
            server_secret_key="2",
            database_name="3",
        )

        bad_server_access_key_db = VuMarkDatabase(server_access_key="1")
        bad_server_secret_key_db = VuMarkDatabase(server_secret_key="2")
        bad_database_name_db = VuMarkDatabase(database_name="3")

        server_access_key_conflict_error = (
            "All server access keys must be unique. "
            'There is already a database with the server access key "1".'
        )
        server_secret_key_conflict_error = (
            "All server secret keys must be unique. "
            'There is already a database with the server secret key "2".'
        )
        database_name_conflict_error = (
            "All names must be unique. "
            'There is already a database with the name "3".'
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
    def test_invalid_state_name() -> None:
        """A state name which is not accepted gives a 400 response which
        names the field and the accepted values.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/vumark_databases"
        response = requests.post(
            url=databases_url,
            json={"state_name": "working"},
            timeout=30,
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        (error,) = response.json()["errors"]
        assert error["loc"] == ["state_name"]
        assert error["msg"] == (
            "Value error, Input should be one of 'WORKING', "
            "'PROJECT_SUSPENDED', 'PROJECT_INACTIVE', "
            "'PROJECT_HAS_NO_API_ACCESS'"
        )
        assert not TARGET_MANAGER.vumark_databases


class TestTargetInUnknownDatabase:
    """Tests for target requests which name a database which does not
    exist.
    """

    @staticmethod
    def test_add_to_cloud_database(high_quality_image: io.BytesIO) -> None:
        """Adding a target to an unknown cloud database gives a 404
        response.
        """
        target_url = (
            _EXAMPLE_URL_FOR_TARGET_MANAGER
            + "/cloud_databases/unknown/targets"
        )
        image_base64 = base64.b64encode(
            s=high_quality_image.getvalue(),
        ).decode()
        response = requests.post(
            url=target_url,
            json={
                "name": "example",
                "width": 1,
                "image_base64": image_base64,
                "active_flag": True,
                "processing_time_seconds": 0,
                "application_metadata": None,
                "target_id": uuid.uuid4().hex,
            },
            timeout=30,
        )

        assert response.status_code == HTTPStatus.NOT_FOUND

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("method", "path"),
        argvalues=[
            (HTTPMethod.DELETE, "/targets/example-target-id"),
            (HTTPMethod.PUT, "/targets/example-target-id"),
            (HTTPMethod.POST, "/targets/example-target-id/recognition_counts"),
        ],
        ids=["delete", "update", "set_recognition_counts"],
    )
    def test_change_target_in_cloud_database(
        method: HTTPMethod,
        path: str,
    ) -> None:
        """Changing a target in an unknown cloud database gives a 404
        response.
        """
        response = requests.request(
            method=method,
            url=_EXAMPLE_URL_FOR_TARGET_MANAGER
            + "/cloud_databases/unknown"
            + path,
            json={},
            timeout=30,
        )

        assert response.status_code == HTTPStatus.NOT_FOUND

    @staticmethod
    def test_add_to_vumark_database() -> None:
        """Adding a VuMark target to an unknown VuMark database gives a 404
        response.
        """
        target_url = (
            _EXAMPLE_URL_FOR_TARGET_MANAGER
            + "/vumark_databases/unknown/vumark_targets"
        )
        response = requests.post(
            url=target_url,
            json=VuMarkTarget(name="example").to_dict(),
            timeout=30,
        )

        assert response.status_code == HTTPStatus.NOT_FOUND


class TestDeleteCloudDatabase:
    """Tests for deleting cloud databases from the mock."""

    @staticmethod
    def test_not_found() -> None:
        """
        A 404 error is returned when trying to delete a cloud database
        which does not exist.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        delete_url = databases_url + "/" + "foobar"
        response = requests.delete(url=delete_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.NOT_FOUND

    @staticmethod
    def test_delete_cloud_database() -> None:
        """It is possible to delete a cloud database."""
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        response = requests.post(url=databases_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.CREATED

        data = json.loads(s=response.text)
        delete_url = databases_url + "/" + data["database_name"]
        response = requests.delete(url=delete_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.OK

        response = requests.delete(url=delete_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.NOT_FOUND


class TestDeleteVuMarkDatabase:
    """Tests for deleting VuMark databases from the mock."""

    @staticmethod
    def test_not_found() -> None:
        """
        A 404 error is returned when trying to delete a VuMark database
        which does not exist.
        """
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/vumark_databases"
        delete_url = databases_url + "/" + "foobar"
        response = requests.delete(url=delete_url, json={}, timeout=30)
        assert response.status_code == HTTPStatus.NOT_FOUND

    @staticmethod
    def test_delete_vumark_database() -> None:
        """It is possible to delete a VuMark database."""
        databases_url = _EXAMPLE_URL_FOR_TARGET_MANAGER + "/vumark_databases"
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
        *,
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
        *,
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
        *,
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
        *,
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
        *,
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
        *,
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
        *,
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
        *,
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


class TestVuMarkTargetStatus:
    """Tests for VuMark instance generation when target status is
    validated (Flask app code path).
    """

    @staticmethod
    def test_processing_target_returns_forbidden() -> None:
        """A VuMark target still processing returns 403 when generating
        an instance via the Flask app.
        """
        vumark_target = VuMarkTarget(
            name="processing-target",
            processing_time_seconds=9999,
        )
        vumark_database = VuMarkDatabase(
            vumark_targets=set(),
        )

        vumark_databases_url = (
            _EXAMPLE_URL_FOR_TARGET_MANAGER + "/vumark_databases"
        )
        response = requests.post(
            url=vumark_databases_url,
            json=vumark_database.to_dict(),
            timeout=30,
        )
        assert response.status_code == HTTPStatus.CREATED
        database_data = json.loads(s=response.text)

        vumark_targets_url = (
            f"{vumark_databases_url}"
            f"/{database_data['database_name']}/vumark_targets"
        )
        response = requests.post(
            url=vumark_targets_url,
            json=vumark_target.to_dict(),
            timeout=30,
        )
        assert response.status_code == HTTPStatus.CREATED

        request_path = f"/targets/{vumark_target.target_id}/instances"
        content_type = "application/json"
        content = json.dumps(
            obj={"instance_id": uuid.uuid4().hex},
        ).encode(encoding="utf-8")
        date = rfc_1123_date()
        authorization_string = authorization_header(
            access_key=vumark_database.server_access_key,
            secret_key=vumark_database.server_secret_key,
            method=HTTPMethod.POST,
            content=content,
            content_type=content_type,
            date=date,
            request_path=request_path,
        )

        response = requests.post(
            url="https://vws.vuforia.com" + request_path,
            headers={
                "Accept": "image/png",
                "Authorization": authorization_string,
                "Content-Length": str(object=len(content)),
                "Content-Type": content_type,
                "Date": date,
            },
            data=content,
            timeout=30,
        )

        assert response.status_code == HTTPStatus.FORBIDDEN
        response_json = response.json()
        assert (
            response_json["result_code"]
            == ResultCodes.TARGET_STATUS_NOT_SUCCESS.value
        )


class TestModelTargetWebAPI:
    """Tests for the Model Target Web API through the Flask app."""

    @staticmethod
    def test_standard_dataset_workflow(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A Model Target dataset can be created and downloaded."""
        monkeypatch.setenv(name="PROCESSING_TIME_SECONDS", value="0")
        token_response = requests.post(
            url="https://vws.vuforia.com/oauth2/token",
            auth=("client-id", "client-secret"),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        token = token_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        create_response = requests.post(
            url="https://vws.vuforia.com/modeltargets/datasets",
            headers=headers,
            json=_MODEL_TARGET_DATASET_REQUEST,
            timeout=30,
        )
        dataset_uuid = create_response.json()["uuid"]
        status_response = requests.get(
            url=(
                "https://vws.vuforia.com/modeltargets/datasets/"
                f"{dataset_uuid}/status"
            ),
            headers=headers,
            timeout=30,
        )
        dataset_response = requests.get(
            url=(
                "https://vws.vuforia.com/modeltargets/datasets/"
                f"{dataset_uuid}/dataset"
            ),
            headers=headers,
            timeout=30,
        )

        assert token_response.status_code == HTTPStatus.OK
        assert create_response.status_code == HTTPStatus.CREATED
        assert status_response.json()["status"] == "done"
        with zipfile.ZipFile(
            file=io.BytesIO(initial_bytes=dataset_response.content),
        ) as dataset_zip:
            assert dataset_zip.namelist() == ["MTDataset.dat", "MTDataset.xml"]

    @staticmethod
    def _dataset_status(dataset_uuid: str) -> dict[str, Any]:
        """Return a dataset's status response body from the VWS app."""
        token_response = requests.post(
            url="https://vws.vuforia.com/oauth2/token",
            auth=("client-id", "client-secret"),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        token = token_response.json()["access_token"]
        status_response = requests.get(
            url=(
                "https://vws.vuforia.com/modeltargets/datasets/"
                f"{dataset_uuid}/status"
            ),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        assert status_response.status_code == HTTPStatus.OK
        status_body: dict[str, Any] = status_response.json()
        return status_body

    def test_seeded_generation_failure(self) -> None:
        """A dataset seeded with a generation failure through the target
        manager API reports the failure through the VWS app.
        """
        dataset = ModelTargetDataset(
            request_body=_MODEL_TARGET_DATASET_REQUEST,
            dataset_type=ModelTargetDatasetType.STANDARD,
            processing_time_seconds=0.0,
            generation_failure=ModelTargetGenerationFailure(
                message="Seeded failure",
            ),
            generation_warning=None,
        )
        datasets_url = (
            _EXAMPLE_URL_FOR_TARGET_MANAGER + "/model_target_datasets"
        )
        create_response = requests.post(
            url=datasets_url,
            json=dataset.to_dict(),
            timeout=30,
        )

        assert create_response.status_code == HTTPStatus.CREATED
        status_body = self._dataset_status(dataset_uuid=dataset.uuid_)
        assert status_body["status"] == "failed"
        assert status_body["error"]["message"] == "Seeded failure"

    def test_seeded_generation_warning(self) -> None:
        """A dataset seeded with a generation warning through the target
        manager API reports the warning through the VWS app.
        """
        dataset = ModelTargetDataset(
            request_body=_MODEL_TARGET_DATASET_REQUEST,
            dataset_type=ModelTargetDatasetType.STANDARD,
            processing_time_seconds=0.0,
            generation_failure=None,
            generation_warning=ModelTargetGenerationWarning(
                message="Seeded warning",
            ),
        )
        datasets_url = (
            _EXAMPLE_URL_FOR_TARGET_MANAGER + "/model_target_datasets"
        )
        create_response = requests.post(
            url=datasets_url,
            json=dataset.to_dict(),
            timeout=30,
        )

        assert create_response.status_code == HTTPStatus.CREATED
        status_body = self._dataset_status(dataset_uuid=dataset.uuid_)
        assert status_body["status"] == "done"
        assert status_body["warning"]["message"] == "Seeded warning"

    @staticmethod
    def test_delete_unknown_dataset() -> None:
        """Deleting an unknown dataset from the target manager returns a
        404 response.
        """
        datasets_url = (
            _EXAMPLE_URL_FOR_TARGET_MANAGER + "/model_target_datasets"
        )
        delete_response = requests.delete(
            url=datasets_url + "/" + uuid.uuid4().hex,
            timeout=30,
        )

        assert delete_response.status_code == HTTPStatus.NOT_FOUND


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


_NUM_WRITER_THREADS = 4
_NUM_READER_THREADS = 4
_NUM_REQUESTS_PER_WRITER = 25
# Requests which read the databases iterate the targets of each database, so
# the more targets there are, the longer a request which changes a database
# has to interleave with a request which reads it.
_NUM_EXISTING_TARGETS = 50


@pytest.fixture(name="small_image_base64")
def fixture_small_image_base64() -> str:
    """A base64 encoded image which is quick to process."""
    image_buffer = io.BytesIO()
    image = Image.new(mode="RGB", size=(64, 64), color=(0, 255, 0))
    image.save(fp=image_buffer, format="PNG")
    return base64.b64encode(s=image_buffer.getvalue()).decode(encoding="utf-8")


@pytest.fixture(name="threaded_target_manager_url")
def fixture_threaded_target_manager_url(
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[str]:
    """Serve the target manager application on multiple threads.

    This uses a real server rather than ``responses`` because ``responses``
    handles one request at a time, within the calling thread.
    """
    # The default target rater inspects each image every time that a target is
    # serialized, which makes the many requests in these tests slow.
    monkeypatch.setenv(name="TARGET_RATER", value="perfect")
    # Threads are switched much more often than they are by default, so that
    # requests interleave with each other often enough for these tests to fail
    # in a single run when state is not guarded by a lock.
    original_switch_interval = sys.getswitchinterval()
    sys.setswitchinterval(0.000_001)
    server: BaseWSGIServer = make_server(
        host="127.0.0.1",
        port=0,
        app=TARGET_MANAGER_FLASK_APP,
        threaded=True,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server_thread.join()
        server.server_close()
        sys.setswitchinterval(original_switch_interval)


def _create_cloud_database(*, base_url: str) -> CloudDatabase:
    """Create a cloud database in the target manager."""
    database = CloudDatabase()
    response = requests.post(
        url=f"{base_url}/cloud_databases",
        json=database.to_dict(),
        timeout=30,
    )
    assert response.status_code == HTTPStatus.CREATED
    return database


def _create_image_target(
    *,
    session: requests.Session,
    base_url: str,
    database: CloudDatabase,
    image_base64: str,
) -> requests.Response:
    """Create a target in a given cloud database."""
    return session.post(
        url=f"{base_url}/cloud_databases/{database.database_name}/targets",
        json={
            "name": uuid.uuid4().hex,
            "width": 1,
            "image_base64": image_base64,
            "active_flag": True,
            "processing_time_seconds": 0,
            "application_metadata": None,
            "target_id": uuid.uuid4().hex,
        },
        timeout=30,
    )


def _list_cloud_databases(
    *,
    session: requests.Session,
    base_url: str,
) -> requests.Response:
    """List all cloud databases."""
    return session.get(url=f"{base_url}/cloud_databases", timeout=30)


def _run_concurrently(
    *,
    writer: Callable[[requests.Session], list[requests.Response]],
    reader: Callable[[requests.Session], list[requests.Response]],
) -> list[requests.Response]:
    """Run writers and readers at the same time and return all responses.

    Args:
        writer: A callable which makes requests which change state.  This is
            called once in each writer thread, with a session of its own.
        reader: A callable which makes requests which read state.  This is
            called in each reader thread, with a session of its own, until
            every writer has finished.

    Returns:
        Every response made by the writers and the readers.
    """
    all_responses: list[requests.Response] = []
    writers_finished = threading.Event()

    def run_writer() -> None:
        """Collect the responses of one writer."""
        # ``list.extend`` is atomic, so it needs no lock of its own.
        with requests.Session() as session:
            all_responses.extend(writer(session))

    def run_reader() -> None:
        """Collect the responses of one reader until the writers
        finish.
        """
        with requests.Session() as session:
            while not writers_finished.is_set():
                all_responses.extend(reader(session))

    reader_threads = [
        threading.Thread(target=run_reader) for _ in range(_NUM_READER_THREADS)
    ]
    writer_threads = [
        threading.Thread(target=run_writer) for _ in range(_NUM_WRITER_THREADS)
    ]
    for thread in [*reader_threads, *writer_threads]:
        thread.start()
    for thread in writer_threads:
        thread.join()
    writers_finished.set()
    for thread in reader_threads:
        thread.join()

    return all_responses


class TestConcurrentRequests:
    """Tests for making multiple requests to the target manager at once.

    The Docker containers serve requests on threads, so requests which
    change state can run at the same time as requests which read it.
    """

    @staticmethod
    def test_create_targets_while_listing_databases(
        *,
        threaded_target_manager_url: str,
        small_image_base64: str,
    ) -> None:
        """Adding targets while databases are listed does not error."""
        base_url = threaded_target_manager_url
        database = _create_cloud_database(base_url=base_url)
        with requests.Session() as setup_session:
            for _ in range(_NUM_EXISTING_TARGETS):
                _create_image_target(
                    session=setup_session,
                    base_url=base_url,
                    database=database,
                    image_base64=small_image_base64,
                )

        def writer(session: requests.Session) -> list[requests.Response]:
            """Add targets to the database."""
            return [
                _create_image_target(
                    session=session,
                    base_url=base_url,
                    database=database,
                    image_base64=small_image_base64,
                )
                for _ in range(_NUM_REQUESTS_PER_WRITER)
            ]

        def reader(session: requests.Session) -> list[requests.Response]:
            """List all cloud databases."""
            return [_list_cloud_databases(session=session, base_url=base_url)]

        all_responses = _run_concurrently(writer=writer, reader=reader)

        error_statuses = [
            response.status_code
            for response in all_responses
            if response.status_code not in {HTTPStatus.OK, HTTPStatus.CREATED}
        ]
        assert not error_statuses

        expected_num_targets = _NUM_EXISTING_TARGETS + (
            _NUM_WRITER_THREADS * _NUM_REQUESTS_PER_WRITER
        )
        (matching_database,) = {
            item
            for item in TARGET_MANAGER.cloud_databases
            if item.database_name == database.database_name
        }
        assert len(matching_database.targets) == expected_num_targets

    @staticmethod
    def test_update_targets_while_listing_databases(
        *,
        threaded_target_manager_url: str,
        small_image_base64: str,
    ) -> None:
        """No listing sees a database without a target which is
        updated.
        """
        base_url = threaded_target_manager_url
        database = _create_cloud_database(base_url=base_url)
        database_url = f"{base_url}/cloud_databases/{database.database_name}"
        target_ids = set[str]()
        with requests.Session() as setup_session:
            for _ in range(_NUM_EXISTING_TARGETS):
                response = _create_image_target(
                    session=setup_session,
                    base_url=base_url,
                    database=database,
                    image_base64=small_image_base64,
                )
                target_ids.add(response.json()["target_id"])

        target_ids_to_update = list(target_ids)[:_NUM_WRITER_THREADS]
        target_ids_to_update_lock = threading.Lock()

        def writer(session: requests.Session) -> list[requests.Response]:
            """Update one target repeatedly."""
            with target_ids_to_update_lock:
                target_id = target_ids_to_update.pop()
            return [
                session.put(
                    url=f"{database_url}/targets/{target_id}",
                    json={"name": uuid.uuid4().hex},
                    timeout=30,
                )
                for _ in range(_NUM_REQUESTS_PER_WRITER)
            ]

        def reader(session: requests.Session) -> list[requests.Response]:
            """List all cloud databases."""
            return [_list_cloud_databases(session=session, base_url=base_url)]

        all_responses = _run_concurrently(writer=writer, reader=reader)

        error_statuses = [
            response.status_code
            for response in all_responses
            if response.status_code != HTTPStatus.OK
        ]
        assert not error_statuses

        listings = [
            response.json()
            for response in all_responses
            if response.request.method == HTTPMethod.GET
        ]
        for listing in listings:
            (listed_database,) = [
                item
                for item in listing
                if item["database_name"] == database.database_name
            ]
            listed_target_ids = {
                target["target_id"] for target in listed_database["targets"]
            }
            assert listed_target_ids == target_ids
