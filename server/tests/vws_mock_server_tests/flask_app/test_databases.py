"""Tests for databases through the Flask app."""

from http import HTTPStatus

import pytest
import requests
from pydantic import JsonValue, TypeAdapter

from mock_vws.database import VuMarkDatabase
from mock_vws.target import VuMarkTarget
from vws_mock_server.target_manager import (
    TARGET_MANAGER,
)


def test_add_vu_mark_database_duplicate_keys(target_manager_url: str) -> None:
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

    databases_url = target_manager_url + "/vumark_databases"
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


def test_invalid_state_name(target_manager_url: str) -> None:
    """A state name which is not accepted gives a 400 response which
    names the field and the accepted values.
    """
    databases_url = target_manager_url + "/vumark_databases"
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


def test_add_to_vumark_database(target_manager_url: str) -> None:
    """Adding a VuMark target to an unknown VuMark database gives a 404
    response.
    """
    target_url = (
        target_manager_url + "/vumark_databases/unknown/vumark_targets"
    )
    response = requests.post(
        url=target_url,
        json=VuMarkTarget(name="example").to_dict(),
        timeout=30,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_vu_mark_database_not_found(target_manager_url: str) -> None:
    """
    A 404 error is returned when trying to delete a VuMark database
    which does not exist.
    """
    databases_url = target_manager_url + "/vumark_databases"
    delete_url = databases_url + "/" + "foobar"
    response = requests.delete(url=delete_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_vumark_database(target_manager_url: str) -> None:
    """It is possible to delete a VuMark database."""
    databases_url = target_manager_url + "/vumark_databases"
    response = requests.post(url=databases_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.CREATED

    data = TypeAdapter(type=dict[str, JsonValue]).validate_json(
        response.text,
    )
    database_name = data["database_name"]
    assert isinstance(database_name, str)
    delete_url = databases_url + "/" + database_name
    response = requests.delete(url=delete_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.OK

    response = requests.delete(url=delete_url, json={}, timeout=30)
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(argnames="body", argvalues=["not JSON", "[]"])
def test_vumark_database_requires_object(
    target_manager_url: str, body: str
) -> None:
    """Malformed and non-object VuMark database requests fail without state
    changes.
    """
    response = requests.post(
        url=target_manager_url + "/vumark_databases",
        data=body,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["errors"][0]["loc"] == []
    assert not bool(TARGET_MANAGER.vumark_databases)
