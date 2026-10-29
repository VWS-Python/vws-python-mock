"""Database state shared by the two mock adapters."""

from beartype import beartype

from mock_vws.database import VuMarkDatabase
from mock_vws.target import VuMarkTarget
from vws_mock_contract_tests.fixtures.credentials import VuMarkCloudDatabase


@beartype
def create_vumark_database(
    *,
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> VuMarkDatabase:
    """Return a database with a VuMark target for VuMark instance
    generation.
    """
    vumark_target = VuMarkTarget(
        name="mock-vumark-target",
        target_id=vumark_vuforia_database.target_id,
    )
    processing_target = VuMarkTarget(
        name="mock-processing-vumark-target",
        target_id=vumark_vuforia_database.processing_target_id,
        processing_time_seconds=9999,
    )
    return VuMarkDatabase(
        database_name=vumark_vuforia_database.target_manager_database_name,
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key=vumark_vuforia_database.server_secret_key,
        vumark_targets={vumark_target, processing_target},
    )
