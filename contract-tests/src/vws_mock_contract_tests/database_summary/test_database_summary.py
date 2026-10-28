"""Additional database summary tests."""

import io
import uuid

import pytest
from vws import VWS

from vws_mock_contract_tests.database_summary.helpers import (
    wait_for_image_numbers,
)


@pytest.mark.usefixtures("mock_only_vuforia")
def test_processing_images(
    *,
    vws_client: VWS,
    image_file_success_state_low_rating: io.BytesIO,
) -> None:
    """The number of images in the processing state is returned.

    The mock adapters report processing images immediately. Real Vuforia's
    summaries are not reliable while targets are processing.
    """
    _ = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_success_state_low_rating,
        active_flag=True,
        application_metadata=None,
    )

    wait_for_image_numbers(
        vws_client=vws_client,
        active_images=0,
        inactive_images=0,
        failed_images=0,
        processing_images=1,
    )
