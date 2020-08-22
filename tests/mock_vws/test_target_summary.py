"""
Tests for the mock of the target summary endpoint.
"""

import base64
import datetime
import io
import uuid

import pytest
from _pytest.fixtures import SubRequest
from backports.zoneinfo import ZoneInfo
from vws import VWS
from vws.exceptions import UnknownTarget

from mock_vws._constants import TargetStatuses
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import query


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestTargetSummary:
    """
    Tests for the target summary endpoint.
    """

    def test_target_summary(
        self,
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """
        A target summary is returned.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        name = 'example target name 1234'

        image_data = image_file_failed_state.read()
        image_data_encoded = base64.b64encode(image_data).decode('ascii')

        gmt = ZoneInfo('GMT')

        date_before_add_target = datetime.datetime.now(tz=gmt).date()

        target_id = vws_client.add_target(
            name=name,
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )

        date_after_add_target = datetime.datetime.now(tz=gmt).date()

        report = vws_client.get_target_summary_report(target_id=target_id)
        assert report.status.value == TargetStatuses.PROCESSING.value
        assert report.database_name == vuforia_database.database_name
        assert report.target_name == name

        # In case the date changes while adding a target
        # we allow the date before and after adding the target.

        assert report.upload_date in (
            date_before_add_target,
            date_after_add_target,
        )

        # While processing the tracking rating is -1.
        assert report.tracking_rating == -1
        assert report.total_recos == 0
        assert report.current_month_recos == 0
        assert report.previous_month_recos == 0

    @pytest.mark.parametrize(
        ['image_fixture_name', 'expected_status'],
        [
            ('high_quality_image', TargetStatuses.SUCCESS),
            ('image_file_failed_state', TargetStatuses.FAILED),
        ],
    )
    def test_after_processing(
        self,
        vuforia_database: VuforiaDatabase,
        request: SubRequest,
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

        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )

        target_id = vws_client.add_target(
            name='example',
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
        assert report.status.value == expected_status.value
        assert report.total_recos == 0
        assert report.current_month_recos == 0
        assert report.previous_month_recos == 0


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestActiveFlag:
    """
    Tests for the active flag related parts of the summary.
    """

    @pytest.mark.parametrize('active_flag', [True, False])
    def test_active_flag(
        self,
        vuforia_database: VuforiaDatabase,
        image_file_failed_state: io.BytesIO,
        active_flag: bool,
    ) -> None:
        """
        The active flag of the target is returned.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        target_id = vws_client.add_target(
            name='example',
            width=1,
            image=image_file_failed_state,
            active_flag=active_flag,
            application_metadata=None,
        )
        report = vws_client.get_target_summary_report(target_id=target_id)
        assert report.active_flag == active_flag


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestRecognitionCounts:
    """
    Tests for the recognition counts in the summary.
    """

    def test_recognition(
        self,
        vuforia_database: VuforiaDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        The recognition counts stay at 0 even after recognitions.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        target_id = vws_client.add_target(
            name='example',
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        image_content = high_quality_image.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        query_response = query(
            vuforia_database=vuforia_database,
            body=body,
        )

        [result] = query_response.json()['results']
        assert result['target_id'] == target_id

        report = vws_client.get_target_summary_report(target_id=target_id)
        assert report.status.value == TargetStatuses.SUCCESS.value
        assert report.total_recos == 0
        assert report.current_month_recos == 0
        assert report.previous_month_recos == 0


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    def test_inactive_project(
        self,
        inactive_database: VuforiaDatabase,
    ) -> None:
        """
        The project's active state does not affect getting a target.
        """
        vws_client = VWS(
            server_access_key=inactive_database.server_access_key,
            server_secret_key=inactive_database.server_secret_key,
        )

        with pytest.raises(UnknownTarget):
            vws_client.get_target_summary_report(target_id=uuid.uuid4().hex)
