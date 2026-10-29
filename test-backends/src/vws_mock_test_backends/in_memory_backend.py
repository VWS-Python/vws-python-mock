"""In-memory mock setup and state for the contract-test adapter."""

from collections.abc import Generator

import pytest
from beartype import beartype

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.states import States
from vws_mock_contract_tests.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
    VuMarkCloudDatabase,
)
from vws_mock_test_backends.mock_databases import create_vumark_database

# The in-memory mock which the ``MOCK`` backend is running, if any.
#
# Tests which use APIs of the mock itself, such as seeding recognition counts,
# need the mock which the fixture created. This is a list so that the fixture
# can set and unset it without a ``global`` statement.
_RUNNING_IN_MEMORY_MOCKS: list[MockVWS] = []


@beartype
def running_in_memory_mock() -> MockVWS:
    """The in-memory mock which the ``MOCK`` backend is running.

    Returns:
        The mock which the ``MOCK`` backend set up for the running test.
        Indexing fails if the ``MOCK`` backend is not running.
    """
    return _RUNNING_IN_MEMORY_MOCKS[0]


@beartype
def enable_in_memory_vuforia(
    *,
    working_database: CloudDatabase,
    inactive_cloud_database: CloudDatabase,
    vumark_vuforia_database: VuMarkCloudDatabase,
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
    base_vwq_url: str,
) -> Generator[None]:
    """Test against the in-memory mock Vuforia."""
    assert bool(monkeypatch)
    working_database = CloudDatabase(
        database_id=working_database.database_id,
        database_name=working_database.database_name,
        server_access_key=working_database.server_access_key,
        server_secret_key=working_database.server_secret_key,
        client_access_key=working_database.client_access_key,
        client_secret_key=working_database.client_secret_key,
    )

    inactive_cloud_database = CloudDatabase(
        state=States.PROJECT_INACTIVE,
        database_name=inactive_cloud_database.database_name,
        server_access_key=inactive_cloud_database.server_access_key,
        server_secret_key=inactive_cloud_database.server_secret_key,
        client_access_key=inactive_cloud_database.client_access_key,
        client_secret_key=inactive_cloud_database.client_secret_key,
    )
    vumark_database = create_vumark_database(
        vumark_vuforia_database=vumark_vuforia_database,
    )
    inactive_vumark_db = VuMarkDatabase(
        state=States.PROJECT_INACTIVE,
        database_name=inactive_vumark_database.target_manager_database_name,
        server_access_key=inactive_vumark_database.server_access_key,
        server_secret_key=inactive_vumark_database.server_secret_key,
    )

    with MockVWS(base_vws_url=base_vws_url, base_vwq_url=base_vwq_url) as mock:
        mock.add_cloud_database(cloud_database=working_database)
        mock.add_cloud_database(cloud_database=inactive_cloud_database)
        mock.add_vumark_database(vumark_database=vumark_database)
        mock.add_vumark_database(vumark_database=inactive_vumark_db)
        _RUNNING_IN_MEMORY_MOCKS.append(mock)
        try:
            yield
        finally:
            _RUNNING_IN_MEMORY_MOCKS.remove(mock)


@beartype
def enable_in_memory_model_targets(
    *,
    monkeypatch: pytest.MonkeyPatch,
    base_vws_url: str,
) -> Generator[None]:
    """Test against the in-memory mock Model Target Web API."""
    assert bool(monkeypatch)
    with MockVWS(base_vws_url=base_vws_url):
        yield


@beartype
def seed_in_memory_counts(
    *,
    database_name: str,
    target_id: str,
    current_month_recos: int,
    previous_month_recos: int,
    total_recos: int,
) -> None:
    """Set recognition counts through the running in-memory
    mock.
    """
    del database_name
    running_in_memory_mock().set_target_recognition_counts(
        target_id=target_id,
        current_month_recos=current_month_recos,
        previous_month_recos=previous_month_recos,
        total_recos=total_recos,
    )
