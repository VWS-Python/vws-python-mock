"""Helpers for adding cloud databases to a mock backend.

Each mock has its own way of being given a database, and this module hides
that difference from the tests.
"""

import os

import requests
from beartype import beartype

from mock_vws.database import CloudDatabase
from tests.mock_vws.fixtures.vuforia_backends import (
    VuforiaBackend,
    running_in_memory_mock,
)


@beartype
def add_cloud_database(
    *,
    backend: VuforiaBackend,
    cloud_database: CloudDatabase,
) -> None:
    """Add a cloud database to a mock backend.

    Args:
        backend: The mock backend which the test is running against. Real
            Vuforia's databases cannot be created by a test, so tests which
            add databases use ``mock_only_vuforia``.
        cloud_database: The database to add.
    """
    if backend == VuforiaBackend.MOCK:
        running_in_memory_mock().add_cloud_database(
            cloud_database=cloud_database,
        )
        return

    # The Flask and Docker mock keeps its databases in the target manager
    # service.
    target_manager_base_url = os.environ["TARGET_MANAGER_BASE_URL"]
    response = requests.post(
        url=f"{target_manager_base_url}/cloud_databases",
        json=cloud_database.to_dict(),
        timeout=30,
    )
    response.raise_for_status()
