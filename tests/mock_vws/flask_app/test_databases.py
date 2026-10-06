"""Tests for databases through the Flask app."""

import base64
import io
import uuid
from http import HTTPMethod, HTTPStatus

import pytest
import requests
from pydantic import TypeAdapter
from vws import VWS, CloudRecoService

from mock_vws._flask_server.target_manager import (
    TARGET_MANAGER,
)
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.model_target import (
    JSONValue,
)
from mock_vws.target import VuMarkTarget
from tests.mock_vws.flask_app.helpers import EXAMPLE_URL_FOR_TARGET_MANAGER


def test_add_cloud_database_duplicate_keys() -> None:
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

    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
    _ = requests.post(url=databases_url, json=database.to_dict(), timeout=30)

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


def test_give_no_details(high_quality_image: io.BytesIO) -> None:
    """It is possible to create a cloud database without giving any
    data.
    """
    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
    response = requests.post(url=databases_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.CREATED

    data = TypeAdapter(type=dict[str, JSONValue]).validate_json(
        response.text,
    )

    assert data["targets"] == []
    assert data["state_name"] == "WORKING"
    assert "database_name" in data

    server_access_key = data["server_access_key"]
    server_secret_key = data["server_secret_key"]
    client_access_key = data["client_access_key"]
    client_secret_key = data["client_secret_key"]
    assert isinstance(server_access_key, str)
    assert isinstance(server_secret_key, str)
    assert isinstance(client_access_key, str)
    assert isinstance(client_secret_key, str)

    vws_client = VWS(
        server_access_key=server_access_key,
        server_secret_key=server_secret_key,
    )

    cloud_reco_client = CloudRecoService(
        client_access_key=client_access_key,
        client_secret_key=client_secret_key,
    )

    assert not bool(vws_client.list_targets())
    assert not bool(cloud_reco_client.query(image=high_quality_image))


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
    body: dict[str, JSONValue],
    expected_loc: list[str],
    expected_message: str,
) -> None:
    """A field with an unaccepted value gives a 400 response which
    names the field and describes what is accepted.
    """
    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
    response = requests.post(url=databases_url, json=body, timeout=30)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.headers["Content-Type"] == "application/json"
    (error,) = response.json()["errors"]
    assert error["loc"] == expected_loc
    assert error["msg"] == expected_message
    assert not bool(TARGET_MANAGER.cloud_databases)


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
    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
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


def test_null_field() -> None:
    """A field which cannot be null is rejected when given as null, and
    a field which can be null is accepted.
    """
    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
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


def test_partial_request_rate_limits() -> None:
    """Groups of endpoints which are not given in the request rate
    limits have no limit of their own.
    """
    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
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


def test_add_vu_mark_database_duplicate_keys() -> None:
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

    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/vumark_databases"
    _ = requests.post(url=databases_url, json=database.to_dict(), timeout=30)

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


def test_invalid_state_name() -> None:
    """A state name which is not accepted gives a 400 response which
    names the field and the accepted values.
    """
    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/vumark_databases"
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
    assert not bool(TARGET_MANAGER.vumark_databases)


def test_add_to_cloud_database(high_quality_image: io.BytesIO) -> None:
    """Adding a target to an unknown cloud database gives a 404
    response.
    """
    target_url = (
        EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases/unknown/targets"
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
        url=EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases/unknown" + path,
        json={},
        timeout=30,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_add_to_vumark_database() -> None:
    """Adding a VuMark target to an unknown VuMark database gives a 404
    response.
    """
    target_url = (
        EXAMPLE_URL_FOR_TARGET_MANAGER
        + "/vumark_databases/unknown/vumark_targets"
    )
    response = requests.post(
        url=target_url,
        json=VuMarkTarget(name="example").to_dict(),
        timeout=30,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_cloud_database_not_found() -> None:
    """
    A 404 error is returned when trying to delete a cloud database
    which does not exist.
    """
    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
    delete_url = databases_url + "/" + "foobar"
    response = requests.delete(url=delete_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_cloud_database() -> None:
    """It is possible to delete a cloud database."""
    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
    response = requests.post(url=databases_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.CREATED

    data = TypeAdapter(type=dict[str, JSONValue]).validate_json(
        response.text,
    )
    database_name = data["database_name"]
    assert isinstance(database_name, str)
    delete_url = databases_url + "/" + database_name
    response = requests.delete(url=delete_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.OK

    response = requests.delete(url=delete_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_vu_mark_database_not_found() -> None:
    """
    A 404 error is returned when trying to delete a VuMark database
    which does not exist.
    """
    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/vumark_databases"
    delete_url = databases_url + "/" + "foobar"
    response = requests.delete(url=delete_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_vumark_database() -> None:
    """It is possible to delete a VuMark database."""
    databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/vumark_databases"
    response = requests.post(url=databases_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.CREATED

    data = TypeAdapter(type=dict[str, JSONValue]).validate_json(
        response.text,
    )
    database_name = data["database_name"]
    assert isinstance(database_name, str)
    delete_url = databases_url + "/" + database_name
    response = requests.delete(url=delete_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.OK

    response = requests.delete(url=delete_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.NOT_FOUND
