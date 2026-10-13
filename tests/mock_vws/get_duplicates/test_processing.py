"""Tests for targets in the processing stage."""

import io
import uuid

from vws import VWS
from vws.reports import TargetStatuses


def test_processing(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> None:
    """If a target is in the processing state, it can have duplicates.

    Targets can have duplicates in the processing state.
    """
    processed_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )
    vws_client.wait_for_target_processed(target_id=processed_target_id)

    processing_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )

    duplicates = vws_client.get_duplicate_targets(
        target_id=processed_target_id,
    )

    assert duplicates == []

    duplicates = vws_client.get_duplicate_targets(
        target_id=processing_target_id,
    )

    target_details = vws_client.get_target_record(
        target_id=processing_target_id,
    )

    # There is a race condition here.
    # If getting the target details and getting the duplicates takes longer
    # than the processing time, the target will be in the success state.
    assert target_details.status == TargetStatuses.PROCESSING
    assert duplicates == [processed_target_id]
