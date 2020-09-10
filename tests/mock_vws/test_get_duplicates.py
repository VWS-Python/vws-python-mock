"""
Tests for the mock of the get duplicates endpoint.
"""

import io
import uuid

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import ProjectInactive
from vws.reports import TargetStatuses


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestDuplicates:
    """
    Tests for the mock of the target duplicates endpoint.
    """

    def test_duplicates(
        self,
        high_quality_image: io.BytesIO,
        image_file_success_state_low_rating: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        Target IDs of similar targets are returned.

        In the mock, "similar" means that the images are exactly the same.
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

    def test_status(
        self,
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


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestActiveFlag:
    """
    Tests for the effects of the active flag on duplicate matching.
    """

    def test_active_flag(
        self,
        high_quality_image: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        Targets with `active_flag` set to `False` can have duplicates.
        Targets with `active_flag` set to `False` are not found as duplicates.

        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API#How-To-Check-for-Duplicate-Targets
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


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestProcessing:
    """
    Tests for targets in the processing stage.
    """

    def test_processing(
        self,
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

        assert target_details.status == TargetStatuses.PROCESSING
        assert duplicates == [processed_target_id]


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    def test_inactive_project(
        self,
        inactive_vws_client: VWS,
    ) -> None:
        """
        If the project is inactive, a FORBIDDEN response is returned.
        """
        with pytest.raises(ProjectInactive):
            inactive_vws_client.get_duplicate_targets(
                target_id=uuid.uuid4().hex,
            )
