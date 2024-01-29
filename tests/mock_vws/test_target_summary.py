"""
Tests for the mock of the target summary endpoint.
"""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest
from vws.exceptions.vws_exceptions import UnknownTarget
from vws.reports import TargetStatuses

if TYPE_CHECKING:
    import io

    from mock_vws.database import VuforiaDatabase
    from vws import VWS, CloudRecoService


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestTargetSummary:
    """
    Tests for the target summary endpoint.
    """

    @staticmethod
    @pytest.mark.parametrize("active_flag", [True, False])
    def test_target_summary(
        vws_client: VWS,
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
        *,
        active_flag: bool,
    ) -> None:
        """
        A target summary is returned.
        """
        name = uuid.uuid4().hex
        gmt = ZoneInfo("GMT")
        date_before_add_target = datetime.datetime.now(tz=gmt).date()

        target_id = vws_client.add_target(
            name=name,
            width=1,
            image=image_file_failed_state,
            active_flag=active_flag,
            application_metadata=None,
        )

        date_after_add_target = datetime.datetime.now(tz=gmt).date()

        report = vws_client.get_target_summary_report(target_id=target_id)
        assert report.status == TargetStatuses.PROCESSING
        assert report.database_name == vuforia_database.database_name
        assert report.target_name == name
        assert report.active_flag == active_flag

        # In case the date changes while adding a target
        # we allow the date before and after adding the target.

        assert report.upload_date in {
            date_before_add_target,
            date_after_add_target,
        }

        # While processing the tracking rating is -1.
        assert report.tracking_rating == -1
        assert report.total_recos == 0
        assert report.current_month_recos == 0
        assert report.previous_month_recos == 0

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("image_fixture_name", "expected_status"),
        argvalues=[
            ("high_quality_image", TargetStatuses.SUCCESS),
            ("image_file_failed_state", TargetStatuses.FAILED),
        ],
    )
    def test_after_processing(
        vws_client: VWS,
        request: pytest.FixtureRequest,
        image_fixture_name: str,
        expected_status: TargetStatuses,
    ) -> None:
        """
        After processing is completed, the tracking rating is in the range of
        0 to 5.

        The documentation says:

        > Note: tracking_rating and reco_rating are provided only when
        > status = success.

        However, this shows that ``tracking_rating`` is given when the status
        is not success.
        It also shows that ``reco_rating`` is not provided even when the status
        is success.
        """
        image_file = request.getfixturevalue(image_fixture_name)

        target_id = vws_client.add_target(
            name="example",
            width=1,
            image=image_file,
            active_flag=True,
            application_metadata=None,
        )

        # The tracking rating may change during processing.
        # Therefore we wait until processing ends.
        vws_client.wait_for_target_processed(target_id=target_id)

        report = vws_client.get_target_summary_report(target_id=target_id)
        target_details = vws_client.get_target_record(target_id=target_id)

        tracking_rating = target_details.target_record.tracking_rating
        assert report.tracking_rating == tracking_rating
        assert report.tracking_rating in range(6)
        assert report.status == expected_status
        assert report.total_recos == 0
        assert report.current_month_recos == 0
        assert report.previous_month_recos == 0


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestRecognitionCounts:
    """
    Tests for the recognition counts in the summary.
    """

    @staticmethod
    def test_recognition(
        vws_client: VWS,
        cloud_reco_client: CloudRecoService,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        The recognition counts stay at 0 even after recognitions.
        """
        target_id = vws_client.add_target(
            name="example",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        results = cloud_reco_client.query(image=high_quality_image)
        (result,) = results
        assert result.target_id == target_id

        report = vws_client.get_target_summary_report(target_id=target_id)
        assert report.status == TargetStatuses.SUCCESS
        assert report.total_recos == 0
        assert report.current_month_recos == 0
        assert report.previous_month_recos == 0


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
            inactive_vws_client.get_target_summary_report(
                target_id=uuid.uuid4().hex,
            )
