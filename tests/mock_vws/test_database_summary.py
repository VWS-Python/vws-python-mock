"""
Tests for the mock of the database summary endpoint.
"""
from __future__ import annotations

import logging
import time
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from mock_vws import MockVWS
from mock_vws.database import VuforiaDatabase
from vws import VWS, CloudRecoService
from vws.exceptions.vws_exceptions import Fail

if TYPE_CHECKING:
    import io

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


def _wait_for_image_numbers(
    vws_client: VWS,
    active_images: int,
    inactive_images: int,
    failed_images: int,
    processing_images: int,
) -> None:
    """
    Wait up to 500 seconds (arbitrary, though we saw timeouts with 300 seconds)
    for the number of images in various categories to match the expected
    number.

    This is necessary because the database summary endpoint lags behind the
    real data.

    This is susceptible to false positives because if, for example, we expect
    no images, and the endpoint adds images with a delay, we will not know.

    Args:
        vws_client: The client to use to connect to Vuforia.
        active_images: The expected number of active images.
        inactive_images: The expected number of inactive images.
        failed_images: The expected number of failed images.
        processing_images: The expected number of processing images.

    Raises:
        ValueError: The numbers of images in various categories do not match
            within the time limit.
    """
    requirements = {
        "active_images": active_images,
        "inactive_images": inactive_images,
        "failed_images": failed_images,
        "processing_images": processing_images,
    }

    maximum_wait_seconds = 500
    start_time = time.monotonic()

    # If we wait for all requirements to match at the same time,
    # we will often not reach that.
    # We therefore wait for each requirement to match at least once.

    # We wait 0.2 seconds rather than less than that to decrease the number
    # of calls made to the API, to decrease the likelihood of hitting the
    # request quota.
    sleep_seconds = 0.2

    for key, value in requirements.items():
        while True:
            seconds_waited = time.monotonic() - start_time
            if seconds_waited > maximum_wait_seconds:  # pragma: no cover
                timeout_message = "Timed out waiting"
                raise ValueError(timeout_message)

            report = vws_client.get_database_summary_report()
            relevant_images_in_summary = getattr(report, key)
            if value != relevant_images_in_summary:  # pragma: no cover
                message = (
                    f"Expected {value} `{key}`s. "
                    f"Found {relevant_images_in_summary} `{key}`s."
                )
                LOGGER.debug(message)

                time.sleep(sleep_seconds)

            # This makes the entire test invalid.
            # However, we have found that without this Vuforia is flaky.
            # We have waited over 10 minutes for the summary to change and
            # that is not sustainable in a test suite.
            break


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestDatabaseSummary:
    """
    Tests for the mock of the database summary endpoint at `GET /summary`.
    """

    @staticmethod
    def test_success(
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        It is possible to get a success response.
        """
        report = vws_client.get_database_summary_report()
        assert report.name == vuforia_database.database_name

        _wait_for_image_numbers(
            vws_client=vws_client,
            active_images=0,
            inactive_images=0,
            failed_images=0,
            processing_images=0,
        )

    @staticmethod
    def test_active_images(
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """
        The number of images in the active state is returned.
        """
        vws_client.wait_for_target_processed(target_id=target_id)

        _wait_for_image_numbers(
            vws_client=vws_client,
            active_images=1,
            inactive_images=0,
            failed_images=0,
            processing_images=0,
        )

    @staticmethod
    def test_failed_images(
        image_file_failed_state: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        The number of images with a 'failed' status is returned.
        """
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        _wait_for_image_numbers(
            vws_client=vws_client,
            active_images=0,
            inactive_images=0,
            failed_images=1,
            processing_images=0,
        )

    @staticmethod
    def test_inactive_images(
        vws_client: VWS,
        image_file_success_state_low_rating: io.BytesIO,
    ) -> None:
        """
        The number of images with a False active_flag and a 'success' status is
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

        _wait_for_image_numbers(
            vws_client=vws_client,
            active_images=0,
            inactive_images=1,
            failed_images=0,
            processing_images=0,
        )

    @staticmethod
    def test_inactive_failed(
        image_file_failed_state: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        An image with a 'failed' status does not show as inactive.
        """
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_file_failed_state,
            active_flag=False,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        _wait_for_image_numbers(
            vws_client=vws_client,
            active_images=0,
            inactive_images=0,
            failed_images=1,
            processing_images=0,
        )

    @staticmethod
    def test_deleted(
        image_file_failed_state: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        Deleted targets are not shown in the summary.
        """
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)

        _wait_for_image_numbers(
            vws_client=vws_client,
            active_images=0,
            inactive_images=0,
            failed_images=0,
            processing_images=0,
        )


class TestProcessingImages:
    """
    Tests for processing images.

    These tests are run only on the mock, and not the real implementation.

    This is because the real implementation is not reliable.
    This is a documented difference between the mock and the real
    implementation.
    """

    @staticmethod
    def test_processing_images(
        image_file_success_state_low_rating: io.BytesIO,
    ) -> None:
        """
        The number of images in the processing state is returned.
        """
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with MockVWS() as mock:
            mock.add_database(database=database)
            vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=image_file_success_state_low_rating,
                active_flag=True,
                application_metadata=None,
            )

            _wait_for_image_numbers(
                vws_client=vws_client,
                active_images=0,
                inactive_images=0,
                failed_images=0,
                processing_images=1,
            )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestQuotas:
    """
    Tests for quotas and thresholds.
    """

    @staticmethod
    def test_quotas(vws_client: VWS) -> None:
        """
        Quotas are included in the database summary.
        These match the quotas given for a free license.
        """
        report = vws_client.get_database_summary_report()
        expected_target_quota = 1000
        expected_request_quota = 100000
        expected_reco_threshold = 1000
        assert report.target_quota == expected_target_quota
        assert report.request_quota == expected_request_quota
        assert report.reco_threshold == expected_reco_threshold


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestRecos:
    """
    Tests for the recognition count fields.
    """

    @staticmethod
    def test_query_request(
        cloud_reco_client: CloudRecoService,
        high_quality_image: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        The ``*_recos`` counts seem to be delayed by a significant amount of
        time.

        We therefore test that they exist, are integers and do not change
        between quick requests.
        """
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id)

        report_before = vws_client.get_database_summary_report()
        cloud_reco_client.query(image=high_quality_image)

        report_after = vws_client.get_database_summary_report()
        assert report_before.total_recos == report_after.total_recos
        assert (
            report_before.current_month_recos
            == report_after.current_month_recos
        )
        assert (
            report_before.previous_month_recos
            == report_after.previous_month_recos
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestRequestUsage:
    """
    Tests for the ``request_usage`` field.
    """

    @staticmethod
    def test_target_request(vws_client: VWS) -> None:
        """
        The ``request_usage`` count does not increase with each request to the
        target API.
        """
        report = vws_client.get_database_summary_report()
        original_request_usage = report.request_usage

        report = vws_client.get_database_summary_report()
        new_request_usage = report.request_usage
        assert new_request_usage == original_request_usage

    @staticmethod
    def test_bad_target_request(
        high_quality_image: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        The ``request_usage`` count does not increase with each request to the
        target API, even if it is a bad request.
        """
        report = vws_client.get_database_summary_report()
        original_request_usage = report.request_usage

        with pytest.raises(Fail) as exc:
            vws_client.add_target(
                name="example",
                width=-1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )

        assert exc.value.response.status_code == HTTPStatus.BAD_REQUEST

        report = vws_client.get_database_summary_report()
        new_request_usage = report.request_usage
        assert new_request_usage == original_request_usage

    @staticmethod
    def test_query_request(
        cloud_reco_client: CloudRecoService,
        high_quality_image: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """
        The ``request_usage`` count does not increase with each query.
        """
        report = vws_client.get_database_summary_report()
        original_request_usage = report.request_usage
        cloud_reco_client.query(image=high_quality_image)
        report = vws_client.get_database_summary_report()
        new_request_usage = report.request_usage
        # The request usage goes up for the database summary request, not the
        # query.
        assert new_request_usage == original_request_usage


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    @staticmethod
    def test_inactive_project(
        inactive_vws_client: VWS,
    ) -> None:
        """
        The project's active state does not affect the database summary.
        """
        inactive_vws_client.get_database_summary_report()
