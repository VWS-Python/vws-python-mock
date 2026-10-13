"""Additional database summary tests."""

import io
import uuid

from vws import VWS

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase
from tests.mock_vws.database_summary.helpers import (
    wait_for_image_numbers,
)


def test_processing_images(
    image_file_success_state_low_rating: io.BytesIO,
) -> None:
    """The number of images in the processing state is returned.

    These tests are run only on the mock, and not the real
    implementation.

    This is because the real implementation is not reliable. This is a
    documented difference between the mock and the real implementation.
    """
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
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
