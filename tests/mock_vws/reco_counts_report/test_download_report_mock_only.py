"""Tests for downloading a report which cannot run against real
Vuforia.

Nothing sets recognition counts on real Vuforia, the mock's generation
time is known where real Vuforia's is not, and only real Vuforia can sign
a URL for its storage.
"""

import datetime
import io
import uuid
from http import HTTPStatus
from urllib.parse import urlsplit, urlunsplit

import pytest
import requests
from beartype import BeartypeConf, beartype
from freezegun import freeze_time

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.reco_counts_report.helpers import (
    CSV_HEADER,
    CURRENT_MONTH_RECOS,
    PREVIOUS_MONTH_RECOS,
    TOTAL_RECOS,
    assert_not_ready,
    get_presigned_url,
    make_vws_client,
    month_offset_from_now,
    report_key,
    wait_for_report,
)
from tests.mock_vws.utils.recognition_counts import seed_recognition_counts


def test_not_ready(*, fresh_database: CloudDatabase) -> None:
    """Until the report is generated, the URL gives the response which
    storage gives for a missing object.
    """
    presigned_url = get_presigned_url(
        vuforia_database=fresh_database,
        month=month_offset_from_now(months=0),
    )

    response = requests.get(url=presigned_url, timeout=30)

    assert_not_ready(
        response=response,
        key=report_key(url=presigned_url),
    )


def test_unknown_report(*, vuforia_database: CloudDatabase) -> None:
    """A file which no request generated gives the response which
    storage gives for a missing object.

    Real Vuforia refuses such a URL because its signature does not match
    the file, and the mock does not check signatures.
    """
    presigned_url = get_presigned_url(
        vuforia_database=vuforia_database,
        month=month_offset_from_now(months=0),
    )
    split_url = urlsplit(url=presigned_url)
    database_id = vuforia_database.database_id
    unknown_path = f"/reports/{database_id}/1999-01.csv"
    unknown_url = urlunsplit(
        components=split_url._replace(path=unknown_path),
    )

    response = requests.get(url=unknown_url, timeout=30)

    assert_not_ready(response=response, key=unknown_path.lstrip("/"))


@pytest.mark.parametrize(
    argnames=("months_ago", "expected_reco_count"),
    argvalues=[
        (0, CURRENT_MONTH_RECOS),
        (1, PREVIOUS_MONTH_RECOS),
    ],
    ids=["current_month", "previous_month"],
)
def test_seeded_recognition_counts(
    *,
    mock_only_vuforia: VuforiaBackend,
    fresh_database: CloudDatabase,
    high_quality_image: io.BytesIO,
    image_file_failed_state: io.BytesIO,
    months_ago: int,
    expected_reco_count: int,
) -> None:
    """The report has a row for each target recognized in the
    month.
    """
    vws_client = make_vws_client(database=fresh_database)
    recognized_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )
    unrecognized_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_failed_state,
        active_flag=True,
        application_metadata=None,
    )
    seed_recognition_counts(
        backend=mock_only_vuforia,
        vuforia_database=fresh_database,
        target_id=recognized_target_id,
        current_month_recos=CURRENT_MONTH_RECOS,
        previous_month_recos=PREVIOUS_MONTH_RECOS,
        total_recos=TOTAL_RECOS,
    )
    presigned_url = get_presigned_url(
        vuforia_database=fresh_database,
        month=month_offset_from_now(months=-months_ago),
    )

    ready_response = wait_for_report(presigned_url=presigned_url)

    assert ready_response.text == (
        f"{CSV_HEADER}{recognized_target_id},{expected_reco_count}\r\n"
    )
    assert unrecognized_target_id not in ready_response.text


def test_counts_set_after_first_request(
    *,
    mock_only_vuforia: VuforiaBackend,
    fresh_database: CloudDatabase,
    high_quality_image: io.BytesIO,
) -> None:
    """A second request in the same hour does not generate the report
    again, so counts set between the two requests are not in it.
    """
    vws_client = make_vws_client(database=fresh_database)
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )
    month = month_offset_from_now(months=0)
    first_url = get_presigned_url(
        vuforia_database=fresh_database,
        month=month,
    )
    seed_recognition_counts(
        backend=mock_only_vuforia,
        vuforia_database=fresh_database,
        target_id=target_id,
        current_month_recos=CURRENT_MONTH_RECOS,
        previous_month_recos=PREVIOUS_MONTH_RECOS,
        total_recos=TOTAL_RECOS,
    )
    second_url = get_presigned_url(
        vuforia_database=fresh_database,
        month=month,
    )
    ready_response = wait_for_report(presigned_url=second_url)

    # If the requests straddled an hour boundary, the second one names a
    # new file, and nothing is claimed about that.
    same_file = urlsplit(url=first_url).path == urlsplit(url=second_url).path
    assert not same_file or ready_response.text == CSV_HEADER


@pytest.mark.parametrize(
    argnames="processing_time_seconds",
    argvalues=[
        pytest.param(60, id="integer"),
        pytest.param(60.0, id="float"),
        pytest.param(0.5, id="fractional"),
    ],
)
@beartype(conf=BeartypeConf(is_pep484_tower=True))
def test_report_processing_time(*, processing_time_seconds: float) -> None:
    """Integer and float delays make reports ready at their completion
    time.
    """
    database = CloudDatabase()
    with (
        freeze_time(time_to_freeze="2026-10-13 12:00:00") as frozen_time,
        MockVWS(processing_time_seconds=processing_time_seconds) as mock,
    ):
        mock.add_cloud_database(cloud_database=database)
        presigned_url = get_presigned_url(
            vuforia_database=database,
            month=month_offset_from_now(months=0),
        )
        response = requests.get(url=presigned_url, timeout=30)
        assert_not_ready(response=response, key=report_key(url=presigned_url))

        _ = frozen_time.tick(
            delta=datetime.timedelta(seconds=processing_time_seconds),
        )
        response = requests.get(url=presigned_url, timeout=30)
        assert response.status_code == HTTPStatus.OK
        assert response.text == CSV_HEADER
