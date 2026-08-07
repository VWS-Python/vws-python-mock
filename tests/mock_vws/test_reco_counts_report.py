"""Tests for the mock of the reco counts report endpoint."""

import datetime
import json
import time
import uuid
from http import HTTPMethod, HTTPStatus
from string import hexdigits
from zoneinfo import ZoneInfo

import pytest
import requests
from beartype import beartype
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import CloudDatabase

_VWS_HOST = "https://vws.vuforia.com"
# The number of seconds which the mocks take to generate a report.
# This matches the default processing time of the mocks.
_GENERATION_TIME_SECONDS = 2


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
    month: str | int,
) -> requests.Response:
    """Request a reco counts report and return the response."""
    # The mocks accept any database ID, and the test credentials do not
    # include the ID of the real database.
    database_id = uuid.uuid4().hex
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


@pytest.mark.usefixtures("mock_only_vuforia")
class TestRecoCountsReport:
    """Tests for requesting a reco counts report.

    These are tested against the mocks only.
    Real Vuforia returns a 401 response for a request which is signed with
    valid server keys but which names a database ID that the keys do not
    belong to, and the test credentials do not include a database ID.
    """

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
            month=month,
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        response_json = json.loads(s=response.text)
        assert response_json["result_code"] == ResultCodes.FAIL.value


@pytest.mark.usefixtures("mock_only_vuforia")
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
            month=_month_offset_from_now(months=0),
        )
        presigned_url = json.loads(s=response.text)["presigned_url"]

        not_ready_response = requests.get(url=presigned_url, timeout=30)
        assert not_ready_response.status_code == HTTPStatus.NOT_FOUND

        time.sleep(_GENERATION_TIME_SECONDS + 1)

        ready_response = requests.get(url=presigned_url, timeout=30)
        assert ready_response.status_code == HTTPStatus.OK
        assert ready_response.headers["Content-Type"] == "text/csv"
        assert ready_response.text == "target_id,reco_count\n"

    @staticmethod
    def test_unknown_report() -> None:
        """An unknown report is not available."""
        url = f"{_VWS_HOST}/reports/recoCounts/{uuid.uuid4().hex}"
        response = requests.get(url=url, timeout=30)

        assert response.status_code == HTTPStatus.NOT_FOUND
