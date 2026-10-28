"""Tests for targets with the status "failed"."""

import io
import uuid

from vws import VWS, CloudRecoService


def test_status_failed(
    *,
    image_file_failed_state: io.BytesIO,
    vws_client: VWS,
    cloud_reco_client: CloudRecoService,
) -> None:
    """Targets with the status "failed" are not found in query results."""
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_failed_state,
        active_flag=True,
        application_metadata=None,
    )
    vws_client.wait_for_target_processed(target_id=target_id)

    results = cloud_reco_client.query(image=image_file_failed_state)
    assert results == []
