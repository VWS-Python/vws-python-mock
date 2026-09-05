"""Tests for the mock of the reco counts report endpoint."""

import datetime
import io
import json
import time
import uuid
from http import HTTPMethod, HTTPStatus
from string import hexdigits
from zoneinfo import ZoneInfo

import pytest
import requests
from beartype import beartype
from vws import VWS
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import CloudDatabase
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.utils.recognition_counts import seed_recognition_counts
from tests.mock_vws.verification import UnverifiedReason, mock_only

_VWS_HOST = "https://vws.vuforia.com"
# The number of seconds which the mocks take to generate a report.
# This matches the default processing time of the mocks.
_GENERATION_TIME_SECONDS = 2
# The recognition counts which the seeded tests set on a target.
_CURRENT_MONTH_RECOS = 3
_PREVIOUS_MONTH_RECOS = 5
_TOTAL_RECOS = 8


@beartype
def _month_offset_from_now(*, months: int) -> str:
    """Return a month in ``YYYY-mm`` form, offset from the current
    month.
    """
    now = datetime.datetime.now(tz=ZoneInfo(key="UTC"))
    total_months = now.year * 12 + now.month - 1 + months
    year, month_index = divmod(total_months, 12)
    return f"{year:04d}-{month_index + 1:02d}"


@beartype
def _request_reco_counts_report(
    *,
    vuforia_database: CloudDatabase,
    database_id: str,
    month: str | int,
) -> requests.Response:
    """Request a reco counts report and return the response.

    The report is requested for the database named by the given ID, and the
    request is signed with the given database's server keys.
    """
    request_path = f"/imagetargets/databases/{database_id}/reports/recoCounts"
    content_type = "application/json"
    content = json.dumps(obj={"month": month}).encode(encoding="utf-8")
    date = rfc_1123_date()
    authorization_string = authorization_header(
        access_key=vuforia_database.server_access_key,
        secret_key=vuforia_database.server_secret_key,
        method=HTTPMethod.POST,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    return requests.post(
        url=_VWS_HOST + request_path,
        headers={
            "Authorization": authorization_string,
            "Content-Length": str(object=len(content)),
            "Content-Type": content_type,
            "Date": date,
        },
        data=content,
        timeout=30,
    )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestRecoCountsReport:
    """Tests for requesting a reco counts report."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames="months_ago",
        argvalues=[0, 1],
        ids=["current_month", "previous_month"],
    )
    def test_reco_counts_report(
        *,
        vuforia_database: CloudDatabase,
        months_ago: int,
    ) -> None:
        """A report can be requested for the current and previous
        month.
        """
        response = _request_reco_counts_report(
            vuforia_database=vuforia_database,
            database_id=vuforia_database.database_id,
            month=_month_offset_from_now(months=-months_ago),
        )

        assert response.status_code == HTTPStatus.OK
        response_json = json.loads(s=response.text)
        assert response_json.keys() == {
            "result_code",
            "transaction_id",
            "presigned_url",
        }
        assert response_json["result_code"] == ResultCodes.SUCCESS.value
        transaction_id = response_json["transaction_id"]
        assert all(char in hexdigits for char in transaction_id)
        assert response_json["presigned_url"].startswith("https://")

    @staticmethod
    @pytest.mark.parametrize(
        argnames="months_ago",
        argvalues=[2, -1],
        ids=["too_old", "in_the_future"],
    )
    def test_month_out_of_range(
        *,
        vuforia_database: CloudDatabase,
        months_ago: int,
    ) -> None:
        """Only the current and the previous month can be requested."""
        response = _request_reco_counts_report(
            vuforia_database=vuforia_database,
            database_id=vuforia_database.database_id,
            month=_month_offset_from_now(months=-months_ago),
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        response_json = json.loads(s=response.text)
        assert response_json["result_code"] == ResultCodes.FAIL.value

    @staticmethod
    @pytest.mark.parametrize(
        argnames="month",
        argvalues=["2020", "2020-1", "January", "2020-01-01", 202001],
        ids=["year_only", "one_digit", "name", "date", "not_a_string"],
    )
    def test_malformed_month(
        *,
        vuforia_database: CloudDatabase,
        month: str | int,
    ) -> None:
        """The month must be given in the ``YYYY-mm`` form."""
        response = _request_reco_counts_report(
            vuforia_database=vuforia_database,
            database_id=vuforia_database.database_id,
            month=month,
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        response_json = json.loads(s=response.text)
        assert response_json["result_code"] == ResultCodes.FAIL.value

    @staticmethod
    def test_unknown_database_id(*, vuforia_database: CloudDatabase) -> None:
        """The path must name the database which the request's server
        keys belong to.
        """
        response = _request_reco_counts_report(
            vuforia_database=vuforia_database,
            database_id=uuid.uuid4().hex,
            month=_month_offset_from_now(months=0),
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        response_json = json.loads(s=response.text)
        assert (
            response_json["result_code"]
            == ResultCodes.AUTHENTICATION_FAILURE.value
        )

    @staticmethod
    def test_database_name_in_path(
        *,
        vuforia_database: CloudDatabase,
    ) -> None:
        """A database is named in the path by its ID, not by its name."""
        response = _request_reco_counts_report(
            vuforia_database=vuforia_database,
            database_id=vuforia_database.database_name,
            month=_month_offset_from_now(months=0),
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        response_json = json.loads(s=response.text)
        assert (
            response_json["result_code"]
            == ResultCodes.AUTHENTICATION_FAILURE.value
        )


@pytest.mark.usefixtures("mock_only_vuforia")
@mock_only(
    reason=UnverifiedReason.INHERENTLY_UNVERIFIABLE,
    detail=(
        "A real report takes between a few seconds and one hour to generate, "
        "and real recognition counts lag behind queries by longer than a test "
        "runs, so no test can download a real report with rows in it."
    ),
)
class TestDownloadReport:
    """Tests for downloading a generated reco counts report.

    Downloads are tested against the mocks only.
    Real Vuforia takes between a few seconds and one hour to generate a
    report, which is too long to wait for in a test.
    """

    @staticmethod
    def test_download_report(*, vuforia_database: CloudDatabase) -> None:
        """The report is available from the given URL once it is ready."""
        response = _request_reco_counts_report(
            vuforia_database=vuforia_database,
            database_id=vuforia_database.database_id,
            month=_month_offset_from_now(months=0),
        )
        presigned_url = json.loads(s=response.text)["presigned_url"]

        not_ready_response = requests.get(url=presigned_url, timeout=30)
        assert not_ready_response.status_code == HTTPStatus.NOT_FOUND

        time.sleep(_GENERATION_TIME_SECONDS + 1)

        ready_response = requests.get(url=presigned_url, timeout=30)
        assert ready_response.status_code == HTTPStatus.OK
        assert ready_response.headers["Content-Type"] == "text/plain"
        assert ready_response.text == "target_id,reco_count\r\n"

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("months_ago", "expected_reco_count"),
        argvalues=[
            (0, _CURRENT_MONTH_RECOS),
            (1, _PREVIOUS_MONTH_RECOS),
        ],
        ids=["current_month", "previous_month"],
    )
    def test_seeded_recognition_counts(
        *,
        mock_only_vuforia: VuforiaBackend,
        vws_client: VWS,
        vuforia_database: CloudDatabase,
        high_quality_image: io.BytesIO,
        image_file_failed_state: io.BytesIO,
        months_ago: int,
        expected_reco_count: int,
    ) -> None:
        """The report has a row for each target recognized in the month.

        Nothing sets recognition counts on real Vuforia, so this runs
        against the mocks only.
        """
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
            vuforia_database=vuforia_database,
            target_id=recognized_target_id,
            current_month_recos=_CURRENT_MONTH_RECOS,
            previous_month_recos=_PREVIOUS_MONTH_RECOS,
            total_recos=_TOTAL_RECOS,
        )

        response = _request_reco_counts_report(
            vuforia_database=vuforia_database,
            database_id=vuforia_database.database_id,
            month=_month_offset_from_now(months=-months_ago),
        )
        presigned_url = json.loads(s=response.text)["presigned_url"]

        time.sleep(_GENERATION_TIME_SECONDS + 1)

        ready_response = requests.get(url=presigned_url, timeout=30)
        assert ready_response.status_code == HTTPStatus.OK
        assert ready_response.text == (
            "target_id,reco_count\r\n"
            f"{recognized_target_id},{expected_reco_count}\r\n"
        )
        assert unrecognized_target_id not in ready_response.text

    @staticmethod
    def test_unknown_report() -> None:
        """An unknown report is not available."""
        url = f"{_VWS_HOST}/reports/recoCounts/{uuid.uuid4().hex}"
        response = requests.get(url=url, timeout=30)

        assert response.status_code == HTTPStatus.NOT_FOUND
