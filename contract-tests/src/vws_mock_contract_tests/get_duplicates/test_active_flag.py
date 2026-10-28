"""Tests for the effects of the active flag on duplicate matching."""

import io
import uuid

from vws import VWS


def test_active_flag(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> None:
    """Targets with `active_flag` set to `False` can have duplicates.
    Targets with `active_flag` set to `False` are not found as
    duplicates.

    https://developer.vuforia.com/library/web-api/cloud-targets-web-services-api#check
    says:

    '''
    If a target is explicitly inactivated through the VWS API (or through
    the Target Manager), then this target is no longer taken into account
    for the duplicate target check.
    '''
    """
    original_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=False,
        application_metadata=None,
    )
    similar_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=original_target_id)
    vws_client.wait_for_target_processed(target_id=similar_target_id)

    duplicates = vws_client.get_duplicate_targets(
        target_id=original_target_id,
    )

    assert duplicates == [similar_target_id]

    duplicates = vws_client.get_duplicate_targets(
        target_id=similar_target_id,
    )

    assert duplicates == []
