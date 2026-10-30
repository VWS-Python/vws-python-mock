"""Tests for databases through the `requests-mock` backend."""

import json

import pytest

from mock_vws import MockVWS
from mock_vws.database import VuMarkDatabase
from mock_vws.target import VuMarkTarget


def test_vumark_database_to_dict() -> None:
    """It is possible to dump a VuMark database to a dictionary and
    load it back.
    """
    vumark_target = VuMarkTarget(
        name="example-vumark",
        processing_time_seconds=3.0,
    )
    database = VuMarkDatabase(
        vumark_targets={vumark_target},
    )

    database_dict = database.to_dict()
    assert bool(json.dumps(obj=database_dict))

    new_database = VuMarkDatabase.from_dict(database_dict=database_dict)
    assert new_database == database


def test_duplicate_vumark_keys() -> None:
    """
    It is not possible to have multiple databases with matching
    keys, including VuMark databases.
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

    with MockVWS() as mock:
        mock.add_vumark_database(vumark_database=database)
        for bad_database, expected_message in (
            (bad_server_access_key_db, server_access_key_conflict_error),
            (bad_server_secret_key_db, server_secret_key_conflict_error),
            (bad_database_name_db, database_name_conflict_error),
        ):
            with pytest.raises(
                expected_exception=ValueError,
                match=expected_message + "$",
            ):
                mock.add_vumark_database(vumark_database=bad_database)


def test_vumark_database_added_before_entering() -> None:
    """A VuMark database added before the mock starts is available
    while the mock is running.
    """
    database = VuMarkDatabase(database_name="vumark-before-enter")
    mock = MockVWS()
    mock.add_vumark_database(vumark_database=database)
    conflicting_database = VuMarkDatabase(
        database_name="vumark-before-enter",
    )
    expected_message = (
        "All names must be unique. "
        "There is already a database with the name "
        '"vumark-before-enter".'
    )
    with (
        mock,
        pytest.raises(
            expected_exception=ValueError,
            match=expected_message + "$",
        ),
    ):
        mock.add_vumark_database(
            vumark_database=conflicting_database,
        )
