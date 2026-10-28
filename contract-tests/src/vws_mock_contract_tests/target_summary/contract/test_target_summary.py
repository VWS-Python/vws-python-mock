"""Tests for the target summary endpoint."""

import datetime as dt
import io
import uuid
from zoneinfo import ZoneInfo

import pytest
from vws import VWS
from vws.reports import TargetStatuses

from vws_mock_contract_tests.fixtures.credentials import (
    NamedCloudDatabaseCredentials,
)
from vws_mock_contract_tests.target_summary.helpers import (
    add_target_and_get_pre_rating_summary,
)


@pytest.mark.parametrize(argnames="active_flag", argvalues=[True, False])
def test_target_summary(
    *,
    vws_client: VWS,
    vuforia_database: NamedCloudDatabaseCredentials,
    image_file_failed_state: io.BytesIO,
    active_flag: bool,
) -> None:
    """A target summary is returned."""
    name = uuid.uuid4().hex
    gmt = ZoneInfo(key="GMT")
    date_before_add_target = dt.datetime.now(tz=gmt).date()

    report = add_target_and_get_pre_rating_summary(
        vws_client=vws_client,
        name=name,
        image_file=image_file_failed_state,
        active_flag=active_flag,
    )

    date_after_add_target = dt.datetime.now(tz=gmt).date()

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
