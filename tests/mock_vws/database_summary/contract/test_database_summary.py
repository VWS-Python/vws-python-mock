"""
Tests for the mock of the database summary endpoint at `GET
/summary`.
"""

import io
import uuid

import pytest
from vws import VWS

from tests.mock_vws.database_summary.helpers import (
    wait_for_image_numbers,
)
from tests.mock_vws.fixtures.credentials import NamedCloudDatabaseCredentials


def test_success(
    *,
    vuforia_database: NamedCloudDatabaseCredentials,
    vws_client: VWS,
) -> None:
    """It is possible to get a success response."""
    report = vws_client.get_database_summary_report()
    assert report.name == vuforia_database.database_name

    wait_for_image_numbers(
        vws_client=vws_client,
        active_images=0,
        inactive_images=0,
        failed_images=0,
        processing_images=0,
    )


# ``verify_mock_vuforia`` is given here as well as on the class so
# that the backend is set up before ``target_id`` adds a target.
@pytest.mark.usefixtures("verify_mock_vuforia", "target_id")
def test_active_images(*, vws_client: VWS) -> None:
    """The number of images in the active state is returned."""
    wait_for_image_numbers(
        vws_client=vws_client,
        active_images=1,
        inactive_images=0,
        failed_images=0,
        processing_images=0,
    )


def test_failed_images(
    *,
    image_file_failed_state: io.BytesIO,
    vws_client: VWS,
) -> None:
    """The number of images with a 'failed' status is returned."""
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_failed_state,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)

    wait_for_image_numbers(
        vws_client=vws_client,
        active_images=0,
        inactive_images=0,
        failed_images=1,
        processing_images=0,
    )


def test_inactive_images(
    *,
    vws_client: VWS,
    image_file_success_state_low_rating: io.BytesIO,
) -> None:
    """
    The number of images with a False active_flag and a 'success'
    status is
    returned.
    """
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_success_state_low_rating,
        active_flag=False,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)

    wait_for_image_numbers(
        vws_client=vws_client,
        active_images=0,
        inactive_images=1,
        failed_images=0,
        processing_images=0,
    )


def test_inactive_failed(
    *,
    image_file_failed_state: io.BytesIO,
    vws_client: VWS,
) -> None:
    """An image with a 'failed' status does not show as inactive."""
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_failed_state,
        active_flag=False,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)

    wait_for_image_numbers(
        vws_client=vws_client,
        active_images=0,
        inactive_images=0,
        failed_images=1,
        processing_images=0,
    )


def test_deleted(
    *,
    image_file_failed_state: io.BytesIO,
    vws_client: VWS,
) -> None:
    """Deleted targets are not shown in the summary."""
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_failed_state,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)
    vws_client.delete_target(target_id=target_id)

    wait_for_image_numbers(
        vws_client=vws_client,
        active_images=0,
        inactive_images=0,
        failed_images=0,
        processing_images=0,
    )
