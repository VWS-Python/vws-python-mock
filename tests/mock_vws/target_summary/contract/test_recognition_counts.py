"""Tests for the recognition counts in the summary."""

import io

from vws import VWS, CloudRecoService
from vws.reports import TargetStatuses


def test_recognition(
    *,
    vws_client: VWS,
    cloud_reco_client: CloudRecoService,
    high_quality_image: io.BytesIO,
) -> None:
    """The recognition counts stay at 0 even after recognitions."""
    target_id = vws_client.add_target(
        name="example",
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)

    results = cloud_reco_client.query(image=high_quality_image)
    (result,) = results
    assert result.target_id == target_id

    report = vws_client.get_target_summary_report(target_id=target_id)
    assert report.status == TargetStatuses.SUCCESS
    assert report.total_recos == 0
    assert report.current_month_recos == 0
    assert report.previous_month_recos == 0
