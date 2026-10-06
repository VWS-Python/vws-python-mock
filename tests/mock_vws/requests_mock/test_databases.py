"""Tests for databases through the `requests-mock` backend."""

import dataclasses
import datetime
import io
import json
from zoneinfo import ZoneInfo

import pytest
from vws import VWS

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.database_type import DatabaseType
from mock_vws.request_rate_limits import (
    DOCUMENTED_REQUEST_RATE_LIMITS,
)
from mock_vws.states import States
from mock_vws.target import ImageTarget, VuMarkTarget
from mock_vws.target_raters import HardcodedTargetTrackingRater


def test_default() -> None:
    """By default, the database has a random name."""
    database_details = CloudDatabase()
    other_database_details = CloudDatabase()
    assert (
        database_details.database_name != other_database_details.database_name
    )


def test_custom_name() -> None:
    """It is possible to set a custom database name."""
    database_details = CloudDatabase(database_name="foo")
    assert database_details.database_name == "foo"


def test_to_dict(high_quality_image: io.BytesIO) -> None:
    """
    It is possible to dump a database to a dictionary and load it
    back.
    """
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    # We test a database with a target added.
    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        _ = vws_client.add_target(
            name="example",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )

    database_dict = database.to_dict()
    # The dictionary is JSON dump-able
    assert bool(json.dumps(obj=database_dict))

    new_database = CloudDatabase.from_dict(database_dict=database_dict)
    assert new_database == database


def test_custom_request_quota() -> None:
    """The request quota survives a dictionary round trip."""
    database = CloudDatabase(request_quota=0)

    database_dict = database.to_dict()
    new_database = CloudDatabase.from_dict(database_dict=database_dict)

    assert new_database.request_quota == 0


def test_custom_target_quota() -> None:
    """The target quota survives a dictionary round trip."""
    database = CloudDatabase(target_quota=0)

    database_dict = database.to_dict()
    new_database = CloudDatabase.from_dict(database_dict=database_dict)

    assert new_database.target_quota == 0


def test_custom_requests_per_second_limit() -> None:
    """The per-second request limit survives a dictionary round
    trip.
    """
    requests_per_second_limit = 12
    database = CloudDatabase(
        requests_per_second_limit=requests_per_second_limit
    )

    database_dict = database.to_dict()
    new_database = CloudDatabase.from_dict(database_dict=database_dict)

    assert new_database.requests_per_second_limit == requests_per_second_limit


def test_custom_request_rate_limits() -> None:
    """Per-endpoint request rate limits survive a dictionary round
    trip.
    """
    database = CloudDatabase(
        request_rate_limits=DOCUMENTED_REQUEST_RATE_LIMITS,
    )

    database_dict = database.to_dict()
    assert bool(json.dumps(obj=database_dict))
    new_database = CloudDatabase.from_dict(database_dict=database_dict)

    assert new_database.request_rate_limits == DOCUMENTED_REQUEST_RATE_LIMITS


def test_round_trip_non_default_fields(
    high_quality_image: io.BytesIO,
) -> None:
    """Every field of a database survives a dictionary round trip."""
    gmt = ZoneInfo(key="GMT")
    target = ImageTarget(
        active_flag=True,
        application_metadata=None,
        image_value=high_quality_image.getvalue(),
        last_modified_date=datetime.datetime(
            year=2020, month=1, day=3, tzinfo=gmt
        ),
        name="example",
        processing_time_seconds=0.5,
        target_tracking_rater=HardcodedTargetTrackingRater(rating=4),
        upload_date=datetime.datetime(year=2020, month=1, day=2, tzinfo=gmt),
        width=1.5,
    )
    database = CloudDatabase(
        client_access_key="example-client-access-key",
        client_secret_key="example-client-secret-key",
        current_month_recos=1,
        database_id="example-database-id",
        database_name="example-database-name",
        # ``CLOUD_RECO`` is the only database type, so it is not
        # possible to use a non-default value here.
        database_type=DatabaseType.CLOUD_RECO,
        previous_month_recos=2,
        reco_threshold=3,
        request_quota=4,
        request_rate_limits=DOCUMENTED_REQUEST_RATE_LIMITS,
        requests_per_second_limit=5,
        server_access_key="example-server-access-key",
        server_secret_key="example-server-secret-key",
        state=States.PROJECT_SUSPENDED,
        target_quota=6,
        targets={target},
        total_recos=7,
    )
    # Adding a field to ``CloudDatabase`` must mean adding it to this
    # test, and therefore to the round trip.
    expected_field_names = {
        "client_access_key",
        "client_secret_key",
        "current_month_recos",
        "database_id",
        "database_name",
        "database_type",
        "previous_month_recos",
        "reco_threshold",
        "request_quota",
        "request_rate_limits",
        "requests_per_second_limit",
        "server_access_key",
        "server_secret_key",
        "state",
        "target_quota",
        "targets",
        "total_recos",
    }
    field_names = {
        field.name
        for field in dataclasses.fields(class_or_instance=CloudDatabase)
    }
    assert field_names == expected_field_names

    database_dict = database.to_dict()
    # The dictionary is JSON dump-able
    assert bool(json.dumps(obj=database_dict))

    new_database = CloudDatabase.from_dict(database_dict=database_dict)
    assert new_database == database


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

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        for bad_database, expected_message in (
            (bad_server_access_key_db, server_access_key_conflict_error),
            (bad_server_secret_key_db, server_secret_key_conflict_error),
            (bad_client_access_key_db, client_access_key_conflict_error),
            (bad_client_secret_key_db, client_secret_key_conflict_error),
            (bad_database_name_db, database_name_conflict_error),
        ):
            with pytest.raises(
                expected_exception=ValueError,
                match=expected_message + "$",
            ):
                mock.add_cloud_database(cloud_database=bad_database)


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


def test_state_is_kept_between_uses(
    high_quality_image: io.BytesIO,
) -> None:
    """A ``MockVWS`` instance keeps its databases, and the targets in
    them, between ``with`` blocks.
    """
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )
    mock = MockVWS()
    mock.add_cloud_database(cloud_database=database)

    with mock:
        _ = vws_client.add_target(
            name="my-target",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        assert len(vws_client.list_targets()) == 1

    with mock:
        assert len(vws_client.list_targets()) == 1
