"""Tests for report timing in the in-memory mock."""

import datetime
from http import HTTPStatus

import pytest
import requests
from beartype import BeartypeConf, beartype
from freezegun import freeze_time

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase
from tests.mock_vws.reco_counts_report.helpers import (
    CSV_HEADER,
    assert_not_ready,
    get_presigned_url,
    month_offset_from_now,
    report_key,
)


@pytest.mark.parametrize(
    argnames="processing_time_seconds",
    argvalues=[
        pytest.param(60, id="integer"),
        pytest.param(60.0, id="float"),
        pytest.param(0.5, id="fractional"),
    ],
)
@beartype(conf=BeartypeConf(is_pep484_tower=True))
def test_report_processing_time(
    *, base_vws_url: str, processing_time_seconds: float
) -> None:
    """Integer and float delays make reports ready at their completion
    time.
    """
    database = CloudDatabase()
    with (
        freeze_time(time_to_freeze="2026-10-13 12:00:00") as frozen_time,
        MockVWS(
            base_vws_url=base_vws_url,
            processing_time_seconds=processing_time_seconds,
        ) as mock,
    ):
        mock.add_cloud_database(cloud_database=database)
        presigned_url = get_presigned_url(
            base_vws_url=base_vws_url,
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
