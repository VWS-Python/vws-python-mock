"""Tests for the mock of the target summary endpoint."""

import datetime
import io
import uuid
from zoneinfo import ZoneInfo

import pytest
from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from vws import VWS, CloudRecoService
from vws.exceptions.vws_exceptions import UnknownTargetError
from vws.reports import TargetStatuses, TargetSummaryReport

from mock_vws.database import CloudDatabase
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.utils.recognition_counts import seed_recognition_counts


@retry(
    # The real VWS reports a tracking rating of -1 for only a short time
    # after an upload, and then the image's rating, even while the target
    # is still processing. The window was observed as roughly one second
    # of a roughly thirty second processing time, and a single poll
    # straight after the upload can miss it (see
    # https://github.com/VWS-Python/vws-python-mock/issues/3354).
    #
    # A rating never returns to -1 once it has left it, so polling the
    # same target again is no use. Instead we retry the whole upload and
    # first poll, with a fresh target each time, until we catch the
    # window. This does not make the assertion certain, only unlikely to
    # fail: the window may sometimes be shorter than one round trip.
    #
    # ``pytest-retry`` does not retry ``AssertionError`` in this suite,
    # so the retry lives here.
    stop=stop_after_attempt(max_attempt_number=5),
    retry=retry_if_exception_type(exception_types=(AssertionError,)),
    reraise=True,
)
def _add_target_and_get_pre_rating_summary(
    *,
    vws_client: VWS,
    name: str,
    image_file: io.BytesIO,
    active_flag: bool,
) -> TargetSummaryReport:
    """Add a target and return its summary report from before it has a
    tracking rating.

    Args:
        vws_client: The client to use to connect to Vuforia.
        name: The name of the target to add.
        image_file: The image to add.
        active_flag: Whether the target should be active.

    Returns:
        The summary report which was taken while the tracking rating
        was still -1.

    Raises:
        AssertionError: The tracking rating was not -1 on any attempt.
    """
    # The client reads the image to its end, so rewind it for each attempt.
    image_file.seek(0)
    target_id = vws_client.add_target(
        name=name,
        width=1,
        image=image_file,
        active_flag=active_flag,
        application_metadata=None,
    )

    report = vws_client.get_target_summary_report(target_id=target_id)
    # While processing the tracking rating is -1.
    assert report.tracking_rating == -1
    return report


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestTargetSummary:
    """Tests for the target summary endpoint."""

    @staticmethod
    @pytest.mark.parametrize(argnames="active_flag", argvalues=[True, False])
    def test_target_summary(
        *,
        vws_client: VWS,
        vuforia_database: CloudDatabase,
        image_file_failed_state: io.BytesIO,
        active_flag: bool,
    ) -> None:
        """A target summary is returned."""
        name = uuid.uuid4().hex
        gmt = ZoneInfo(key="GMT")
        date_before_add_target = datetime.datetime.now(tz=gmt).date()

        report = _add_target_and_get_pre_rating_summary(
            vws_client=vws_client,
            name=name,
            image_file=image_file_failed_state,
            active_flag=active_flag,
        )

        date_after_add_target = datetime.datetime.now(tz=gmt).date()

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
        *,
        vws_client: VWS,
        request: pytest.FixtureRequest,
        image_fixture_name: str,
        expected_status: TargetStatuses,
    ) -> None:
        """After processing is completed, the tracking rating is in the
        range
        of 0 to 5.

        The documentation says:

        > Note: tracking_rating and reco_rating are provided only when
        > status = success.

        However, this shows that ``tracking_rating`` is given when the status
        is not success.
        It also shows that ``reco_rating`` is not provided even when the status
        is success.
        """
        image_file = request.getfixturevalue(argname=image_fixture_name)

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
    """Tests for the recognition counts in the summary."""

    @staticmethod
    def test_recognition(
        *,
        vws_client: VWS,
        cloud_reco_client: CloudRecoService,
        high_quality_image: io.BytesIO,
    ) -> None:
        """The recognition counts stay at 0 even after recognitions."""
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


class TestSeededRecognitionCounts:
    """Tests for the recognition counts which are set on a target.

    Real Vuforia's recognition counts lag behind its queries by longer than
    a test runs, so the mocks let the counts be set rather than counting
    recognitions. Nothing sets counts on real Vuforia, so these tests run
    against the mocks only.
    """

    CURRENT_MONTH_RECOS = 3
    PREVIOUS_MONTH_RECOS = 5
    TOTAL_RECOS = 8

    def test_seeded_counts(
        self,
        *,
        mock_only_vuforia: VuforiaBackend,
        vws_client: VWS,
        vuforia_database: CloudDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """The summary shows the recognition counts set on the target."""
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id)

        seed_recognition_counts(
            backend=mock_only_vuforia,
            vuforia_database=vuforia_database,
            target_id=target_id,
            current_month_recos=self.CURRENT_MONTH_RECOS,
            previous_month_recos=self.PREVIOUS_MONTH_RECOS,
            total_recos=self.TOTAL_RECOS,
        )

        report = vws_client.get_target_summary_report(target_id=target_id)
        assert report.status == TargetStatuses.SUCCESS
        assert report.total_recos == self.TOTAL_RECOS
        assert report.current_month_recos == self.CURRENT_MONTH_RECOS
        assert report.previous_month_recos == self.PREVIOUS_MONTH_RECOS


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """Tests for inactive projects."""

    @staticmethod
    def test_inactive_project(inactive_vws_client: VWS) -> None:
        """The project's active state does not affect getting a target."""
        with pytest.raises(expected_exception=UnknownTargetError):
            inactive_vws_client.get_target_summary_report(
                target_id=uuid.uuid4().hex,
            )
