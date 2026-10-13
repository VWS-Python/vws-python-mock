"""Tests for updated targets."""

import base64
import calendar
import io
import time

from vws import VWS, CloudRecoService


def test_updated_target(
    *,
    high_quality_image: io.BytesIO,
    different_high_quality_image: io.BytesIO,
    vws_client: VWS,
    cloud_reco_client: CloudRecoService,
) -> None:
    """After a target is updated, only the new image can be matched.

    The match result includes the updated name, timestamp and
    application metadata.
    """
    metadata = b"example_metadata"
    metadata_encoded = base64.b64encode(s=metadata).decode(encoding="ascii")
    name = "example_name"
    target_id = vws_client.add_target(
        name=name,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=metadata_encoded,
    )

    _ = calendar.timegm(tuple=time.gmtime())

    vws_client.wait_for_target_processed(target_id=target_id)

    new_name = name + "2"
    new_metadata = metadata + b"2"
    new_metadata_encoded = base64.b64encode(s=new_metadata).decode(
        encoding="ascii"
    )

    results = cloud_reco_client.query(image=high_quality_image)
    (result,) = results
    assert result.target_data is not None
    original_target_timestamp = result.target_data.target_timestamp

    vws_client.update_target(
        target_id=target_id,
        name=new_name,
        image=different_high_quality_image,
        application_metadata=new_metadata_encoded,
    )

    approximate_target_updated = calendar.timegm(tuple=time.gmtime())

    vws_client.wait_for_target_processed(target_id=target_id)

    results = cloud_reco_client.query(image=different_high_quality_image)

    (result,) = results
    assert result.target_data is not None
    assert result.target_data.application_metadata == new_metadata_encoded
    assert result.target_data.name == new_name
    target_timestamp = result.target_data.target_timestamp
    # In the future we might want to test that
    # target_timestamp > original_target_timestamp
    # However, this requires us to set the mock processing time at > 1
    # second.
    assert target_timestamp >= original_target_timestamp
    time_difference = abs(
        approximate_target_updated - target_timestamp.timestamp(),
    )
    max_time_difference = 5
    assert time_difference < max_time_difference

    results = cloud_reco_client.query(image=high_quality_image)
    assert results == []
