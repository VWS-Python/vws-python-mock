"""Fixtures scoped to this group of tests."""

import pytest

from mock_vws.database import CloudDatabase
from tests.mock_vws.utils.cloud_databases import AddCloudDatabase


@pytest.fixture(name="fresh_database")
def fixture_fresh_database(
    *,
    add_cloud_database: AddCloudDatabase,
) -> CloudDatabase:
    """A database which no report has been requested for.

    The shared test database is one database for the whole test run, so a
    backend whose report store outlives a test serves the report which an
    earlier test generated for it, as real Vuforia does with the shared
    real database.
    Tests which need a report which they generated themselves use their own
    database.
    """
    database = CloudDatabase()
    add_cloud_database(cloud_database=database)
    return database


@pytest.fixture(autouse=True)
def fixture_verify_backend(
    *,
    mock_only_vuforia: None,
) -> None:
    """Set up the backend for every contract test in this directory."""
    del mock_only_vuforia
