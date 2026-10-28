"""Tests for active versus inactive targets."""

import io
import uuid

from vws import VWS, CloudRecoService


def test_inactive(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
    cloud_reco_client: CloudRecoService,
) -> None:
    """Images which are not active are not matched."""
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=False,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)
    results = cloud_reco_client.query(image=high_quality_image)
    assert results == []
