"""Fixtures scoped to this group of tests."""

import os

import pytest
import requests

from mock_vws.database import CloudDatabase
from mock_vws.request_rate_limits import DOCUMENTED_REQUEST_RATE_LIMITS
from tests.mock_vws.fixtures.vuforia_backends import (
    VuforiaBackend,
    running_in_memory_mock,
)


@pytest.fixture(name="rate_limited_database")
def fixture_rate_limited_database(
    verify_mock_vuforia: VuforiaBackend,
    vuforia_database: CloudDatabase,
) -> CloudDatabase:
    """Return a database which applies real Vuforia's request rate limits.

    The real database applies them itself. Each mock is given a fresh
    database with the limits, so that the shared database which the other
    tests use is not limited.
    """
    if verify_mock_vuforia == VuforiaBackend.REAL:
        return vuforia_database

    database = CloudDatabase(
        request_rate_limits=DOCUMENTED_REQUEST_RATE_LIMITS
    )
    if verify_mock_vuforia == VuforiaBackend.MOCK:
        running_in_memory_mock().add_cloud_database(cloud_database=database)
        return database

    target_manager_base_url = os.environ["TARGET_MANAGER_BASE_URL"]
    response = requests.post(
        url=f"{target_manager_base_url}/cloud_databases",
        json=database.to_dict(),
        timeout=30,
    )
    response.raise_for_status()
    return database


@pytest.fixture(autouse=True)
def fixture_verify_backend(
    *,
    verify_mock_vuforia: VuforiaBackend,
) -> None:
    """Set up the backend for every contract test in this directory."""
    del verify_mock_vuforia
