"""Helpers for seeding recognition counts on a target.

Neither mock counts recognitions, because real Vuforia's counts lag behind
its queries by longer than a test runs. Each mock instead has its own way of
being told what the counts are, and this module hides that difference from
the tests.
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
def seed_recognition_counts(
    *,
    backend: VuforiaBackend,
    vuforia_database: CloudDatabase,
    target_id: str,
    current_month_recos: int,
    previous_month_recos: int,
    total_recos: int,
) -> None:
    """Set the recognition counts of a target on a mock backend.

    Args:
        backend: The mock backend which the test is running against. Real
            Vuforia's recognition counts cannot be set, so tests which seed
            counts use ``mock_only_vuforia``.
        vuforia_database: The database which the target is in.
        target_id: The ID of the target to set recognition counts of.
        current_month_recos: The number of recognitions of the target in the
            current month.
        previous_month_recos: The number of recognitions of the target in the
            previous month.
        total_recos: The total number of recognitions of the target.
    """
    if backend == VuforiaBackend.MOCK:
        running_in_memory_mock().set_target_recognition_counts(
            target_id=target_id,
            current_month_recos=current_month_recos,
            previous_month_recos=previous_month_recos,
            total_recos=total_recos,
        )
        return

    # The Flask and Docker mock keeps its targets in the target manager
    # service, which is where its recognition counts are set.
    target_manager_base_url = os.environ["TARGET_MANAGER_BASE_URL"]
    database_name = vuforia_database.database_name
    response = requests.post(
        url=(
            f"{target_manager_base_url}/cloud_databases/"
            f"{database_name}/targets/{target_id}/recognition_counts"
        ),
        json={
            "current_month_recos": current_month_recos,
            "previous_month_recos": previous_month_recos,
            "total_recos": total_recos,
        },
        timeout=30,
    )
    response.raise_for_status()
