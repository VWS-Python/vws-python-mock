"""HTTP controls for a mock target-manager service."""

import requests
from beartype import beartype

from mock_vws.database import CloudDatabase


@beartype
def seed_recognition_counts(
    *,
    target_manager_base_url: str,
    database_name: str,
    target_id: str,
    current_month_recos: int,
    previous_month_recos: int,
    total_recos: int,
) -> None:
    """Set recognition counts through the target manager service."""
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


@beartype
def add_cloud_database(
    *, target_manager_base_url: str, cloud_database: CloudDatabase
) -> None:
    """Add a cloud database through the target manager service."""
    response = requests.post(
        url=f"{target_manager_base_url}/cloud_databases",
        json=cloud_database.to_dict(),
        timeout=30,
    )
    response.raise_for_status()
