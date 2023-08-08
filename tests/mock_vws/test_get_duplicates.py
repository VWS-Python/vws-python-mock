"""
Tests for the mock of the get duplicates endpoint.
"""
from __future__ import annotations

import copy
import io
import uuid
from typing import TYPE_CHECKING

import pytest
from PIL import Image
from vws.exceptions.vws_exceptions import ProjectInactive
from vws.reports import TargetStatuses

if TYPE_CHECKING:
    from vws import VWS


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestDuplicates:
    """
    Tests for the mock of the target duplicates endpoint.
    """

    @staticmethod
    def test_duplicates(
        high_quality_image: io.BytesIO,
        image_file_success_state_low_rating: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        Target IDs of the exact same targets are returned.
        """
        image_data = high_quality_image
        different_image_data = image_file_success_state_low_rating

        original_target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_data,
            active_flag=True,
            application_metadata=None,
        )

        similar_target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_data,
            active_flag=True,
            application_metadata=None,
        )

        different_target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=different_image_data,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=original_target_id)
        vws_client.wait_for_target_processed(target_id=similar_target_id)
        vws_client.wait_for_target_processed(target_id=different_target_id)

        duplicates = vws_client.get_duplicate_targets(
            target_id=original_target_id,
        )

        assert duplicates == [similar_target_id]

    @staticmethod
    def test_duplicates_not_same(
        high_quality_image: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        Target IDs of similar targets are returned.
        """
        image_data = high_quality_image
        similar_image_data = copy.copy(image_data)
        similar_image_buffer = io.BytesIO()
        pil_similar_image = Image.open(similar_image_data)
        # Re-save means similar but not identical.
        pil_similar_image.save(similar_image_buffer, format="JPEG")
        assert similar_image_buffer.getvalue() != image_data.getvalue()

        original_target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_data,
            active_flag=True,
            application_metadata=None,
        )

        similar_target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=similar_image_buffer,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=original_target_id)
        vws_client.wait_for_target_processed(target_id=similar_target_id)

        duplicates = vws_client.get_duplicate_targets(
            target_id=original_target_id,
        )

        assert duplicates == [similar_target_id]

    @staticmethod
    def test_status(
        image_file_failed_state: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        Targets are not duplicates if the status is not 'success'.
        """
        original_target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )

        similar_target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=original_target_id)
        vws_client.wait_for_target_processed(target_id=similar_target_id)

        target_details = vws_client.get_target_record(
            target_id=original_target_id,
        )
        assert target_details.status == TargetStatuses.FAILED

        duplicates = vws_client.get_duplicate_targets(
            target_id=original_target_id,
        )

        assert duplicates == []


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestActiveFlag:
    """
    Tests for the effects of the active flag on duplicate matching.
    """

    @staticmethod
    def test_active_flag(
        high_quality_image: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        Targets with `active_flag` set to `False` can have duplicates.
        Targets with `active_flag` set to `False` are not found as duplicates.

        https://library.vuforia.com/web-api/cloud-targets-web-services-api#check
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


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestProcessing:
    """
    Tests for targets in the processing stage.
    """

    @staticmethod
    def test_processing(
        high_quality_image: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        If a target is in the processing state, it can have duplicates.
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


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    @staticmethod
    def test_inactive_project(inactive_vws_client: VWS) -> None:
        """
        If the project is inactive, a FORBIDDEN response is returned.
        """
        with pytest.raises(ProjectInactive):
            inactive_vws_client.get_duplicate_targets(
                target_id=uuid.uuid4().hex,
            )
