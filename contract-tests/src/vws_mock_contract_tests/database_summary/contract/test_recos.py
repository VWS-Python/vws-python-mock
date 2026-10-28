"""Tests for the recognition count fields."""

import io
import uuid

from vws import VWS, CloudRecoService


def test_query_request(
    *,
    cloud_reco_client: CloudRecoService,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> None:
    """Recognition counts update asynchronously after a query."""
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )
    vws_client.wait_for_target_processed(target_id=target_id)

    report_before = vws_client.get_database_summary_report()
    _ = cloud_reco_client.query(image=high_quality_image)

    report_after = vws_client.get_database_summary_report()
    total_recos_change = report_after.total_recos - report_before.total_recos
    current_month_recos_change = (
        report_after.current_month_recos - report_before.current_month_recos
    )
    assert total_recos_change in {0, 1}
    assert current_month_recos_change == total_recos_change
    assert (
        report_before.previous_month_recos == report_after.previous_month_recos
    )
