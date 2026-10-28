"""Tests for the recognition counts which are set on a target.

Real Vuforia's recognition counts lag behind its queries by longer than
a test runs, so the mocks let the counts be set rather than counting
recognitions. Nothing sets counts on real Vuforia, so these tests run
against the mocks only.
"""

import io
import uuid

from vws import VWS
from vws.reports import TargetStatuses

from tests.mock_vws.fixtures.credentials import NamedCloudDatabaseCredentials
from tests.mock_vws.utils.recognition_counts import SeedRecognitionCounts

_CURRENT_MONTH_RECOS = 3
_PREVIOUS_MONTH_RECOS = 5
_TOTAL_RECOS = 8


def test_seeded_counts(
    *,
    seed_recognition_counts: SeedRecognitionCounts,
    vws_client: VWS,
    vuforia_database: NamedCloudDatabaseCredentials,
    high_quality_image: io.BytesIO,
) -> None:
    """The summary shows the recognition counts set on the target."""
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )
    vws_client.wait_for_target_processed(target_id=target_id)

    seed_recognition_counts(
        database_name=vuforia_database.database_name,
        target_id=target_id,
        current_month_recos=_CURRENT_MONTH_RECOS,
        previous_month_recos=_PREVIOUS_MONTH_RECOS,
        total_recos=_TOTAL_RECOS,
    )

    report = vws_client.get_target_summary_report(target_id=target_id)
    assert report.status == TargetStatuses.SUCCESS
    assert report.total_recos == _TOTAL_RECOS
    assert report.current_month_recos == _CURRENT_MONTH_RECOS
    assert report.previous_month_recos == _PREVIOUS_MONTH_RECOS
