"""Shared helpers for get target tests."""

import io
import uuid

from vws import VWS


def get_target_tracking_rating(
    *,
    vws_client: VWS,
    image_file: io.BytesIO,
) -> int:
    """Get the tracking rating of a target with the given image."""
    target_id = vws_client.add_target(
        name=f"example_{uuid.uuid4().hex}",
        width=1,
        image=image_file,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)
    target_details = vws_client.get_target_record(target_id=target_id)
    return target_details.target_record.tracking_rating
