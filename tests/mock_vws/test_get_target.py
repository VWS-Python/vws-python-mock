"""
Tests for getting a target record.

https://library.vuforia.com/web-api/cloud-targets-web-services-api#target-record
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from vws.exceptions.vws_exceptions import UnknownTarget
from vws.reports import TargetRecord, TargetStatuses

if TYPE_CHECKING:
    import io

    from vws import VWS


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestGetRecord:
    """
    Tests for getting a target record.
    """

    @staticmethod
    def test_get_vws_target(
        vws_client: VWS,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        Details of a target are returned.
        """
        name = "my_example_name"
        width = 1234

        target_id = vws_client.add_target(
            name=name,
            width=width,
            image=image_file_failed_state,
            active_flag=False,
            application_metadata=None,
        )
        target_details = vws_client.get_target_record(target_id=target_id)
        target_record = target_details.target_record
        tracking_rating = target_record.tracking_rating

        # Tracking rating may be -1 while processing.
        assert tracking_rating in range(-1, 6)
        target_id = target_record.target_id

        expected_target_record = TargetRecord(
            target_id=target_id,
            active_flag=False,
            name=name,
            width=width,
            tracking_rating=tracking_rating,
            reco_rating="",
        )

        assert target_record == expected_target_record

    @staticmethod
    def test_fail_status(
        vws_client: VWS,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        When a 1x1 image is given, the status changes from 'processing' to
        'failed' after some time.
        """
        target_id = vws_client.add_target(
            name="my_example_name",
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)
        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.status == TargetStatuses.FAILED
        # Tracking rating is 0 when status is 'failed'
        assert target_details.target_record.tracking_rating == 0

    @staticmethod
    def test_success_status(
        image_file_success_state_low_rating: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        When a random, large enough image is given, the status changes from
        'processing' to 'success' after some time.

        The mock is much more lenient than the real implementation of VWS.
        The test image does not prove that what is counted as a success in the
        mock will be counted as a success in the real implementation.
        """
        target_id = vws_client.add_target(
            name="example",
            width=1,
            image=image_file_success_state_low_rating,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.status == TargetStatuses.SUCCESS
        # Tracking rating is between 0 and 5 when status is 'success'
        tracking_rating = target_details.target_record.tracking_rating
        assert tracking_rating in range(6)

        # The tracking rating stays stable across requests
        target_details = vws_client.get_target_record(target_id=target_id)
        new_tracking_rating = target_details.target_record.tracking_rating
        assert new_tracking_rating == tracking_rating


def _get_target_tracking_rating(
    vws_client: VWS,
    image_file: io.BytesIO,
) -> int:
    """
    Get the tracking rating of a target.
    """
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


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestTargetTrackingRating:
    """
    Tests which exercise the target tracking_rating, and check the image
    fixtures we use.
    """

    @staticmethod
    def test_target_quality(
        vws_client: VWS,
        high_quality_image: io.BytesIO,
        image_file_success_state_low_rating: io.BytesIO,
        corrupted_image_file: io.BytesIO,
    ) -> None:
        """
        The target tracking rating is as expected.
        """
        high_quality_image_tracking_rating = _get_target_tracking_rating(
            vws_client=vws_client,
            image_file=high_quality_image,
        )
        low_quality_image_tracking_rating = _get_target_tracking_rating(
            vws_client=vws_client,
            image_file=image_file_success_state_low_rating,
        )
        corrupted_image_file_tracking_rating = _get_target_tracking_rating(
            vws_client=vws_client,
            image_file=corrupted_image_file,
        )
        assert (
            high_quality_image_tracking_rating
            > low_quality_image_tracking_rating
            >= corrupted_image_file_tracking_rating
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    @staticmethod
    def test_inactive_project(inactive_vws_client: VWS) -> None:
        """
        The project's active state does not affect getting a target.
        """
        with pytest.raises(UnknownTarget):
            inactive_vws_client.get_target_record(target_id=uuid.uuid4().hex)
