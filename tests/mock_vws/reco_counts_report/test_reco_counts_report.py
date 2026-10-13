"""Tests for requesting a reco counts report."""

import datetime
import json
import uuid
from http import HTTPStatus
from string import hexdigits
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

import pytest

from mock_vws._constants import ResultCodes
from mock_vws.database import CloudDatabase
from tests.mock_vws.reco_counts_report.helpers import (
    AMZ_DATE_FORMAT,
    PRESIGNED_URL_PARAMETERS,
    URL_EXPIRY_SECONDS,
    get_presigned_url,
    month_offset_from_now,
    request_reco_counts_report,
    request_reco_counts_report_json,
    utc_now,
)


@pytest.mark.parametrize(
    argnames="months_ago",
    argvalues=[0, 1],
    ids=["current_month", "previous_month"],
)
def test_reco_counts_report(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabase,
    months_ago: int,
) -> None:
    """A report can be requested for the current and previous
    month.
    """
    response = request_reco_counts_report(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        database_id=vuforia_database.database_id,
        month=month_offset_from_now(months=-months_ago),
    )

    assert response.status_code == HTTPStatus.OK
    response_json = json.loads(s=response.text)
    assert response_json.keys() == {
        "result_code",
        "transaction_id",
        "presigned_url",
    }
    assert response_json["result_code"] == ResultCodes.SUCCESS.value
    transaction_id: object = response_json["transaction_id"]
    assert isinstance(transaction_id, str)
    assert all(char in hexdigits for char in transaction_id)
    presigned_url: object = response_json["presigned_url"]
    assert isinstance(presigned_url, str)
    download_url = urlsplit(url=presigned_url)
    assert download_url.scheme in {"http", "https"}
    assert download_url.netloc != ""


def test_presigned_url_query(
    *, base_vws_url: str, vuforia_database: CloudDatabase
) -> None:
    """The URL carries the query parameters of a presigned URL.

    It is signed for one second under seven days.
    """
    before = utc_now().replace(microsecond=0)
    presigned_url = get_presigned_url(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        month=month_offset_from_now(months=0),
    )
    after = utc_now()

    query = parse_qsl(qs=urlsplit(url=presigned_url).query)
    assert [name for name, _ in query] == PRESIGNED_URL_PARAMETERS
    parameters = dict(query)
    assert parameters["X-Amz-Security-Token"] != ""
    assert parameters["X-Amz-Algorithm"] == "AWS4-HMAC-SHA256"
    assert parameters["X-Amz-SignedHeaders"] == "host"
    assert parameters["X-Amz-Expires"] == str(object=URL_EXPIRY_SECONDS)
    assert all(char in hexdigits for char in parameters["X-Amz-Signature"])
    signed_at = datetime.datetime.strptime(
        parameters["X-Amz-Date"],
        AMZ_DATE_FORMAT,
    ).replace(tzinfo=ZoneInfo(key="UTC"))
    # Real Vuforia's clock is not the test's clock.
    clock_skew = datetime.timedelta(minutes=5)
    assert before - clock_skew <= signed_at <= after + clock_skew
    signed_date = signed_at.strftime(format="%Y%m%d")
    assert parameters["X-Amz-Credential"].endswith(
        f"/{signed_date}/us-west-1/s3/aws4_request",
    )


def test_current_month_file_name(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabase,
) -> None:
    """A report for the current month is named for the date and the
    hour.
    """
    hours_before = utc_now().strftime(format="%Y-%m-%d-%H")
    presigned_url = get_presigned_url(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        month=month_offset_from_now(months=0),
    )
    hours_after = utc_now().strftime(format="%Y-%m-%d-%H")

    database_id = vuforia_database.database_id
    expected_paths = {
        f"/reports/{database_id}/{hour}.csv"
        for hour in (hours_before, hours_after)
    }
    assert urlsplit(url=presigned_url).path in expected_paths


def test_previous_month_file_name(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabase,
) -> None:
    """A report for the previous month is named for the month."""
    month = month_offset_from_now(months=-1)
    presigned_url = get_presigned_url(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        month=month,
    )

    database_id = vuforia_database.database_id
    expected_path = f"/reports/{database_id}/{month}.csv"
    assert urlsplit(url=presigned_url).path == expected_path


def test_same_file_in_the_same_hour(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabase,
) -> None:
    """Two requests for the current month in the same hour name the
    same file.
    """
    month = month_offset_from_now(months=0)
    first_url = get_presigned_url(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        month=month,
    )
    second_url = get_presigned_url(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        month=month,
    )
    hour_after = utc_now().strftime(format="%Y-%m-%d-%H")

    # If the requests straddled an hour boundary, the second one
    # legitimately names the new hour's file instead.
    database_id = vuforia_database.database_id
    expected_paths = {
        urlsplit(url=first_url).path,
        f"/reports/{database_id}/{hour_after}.csv",
    }
    assert urlsplit(url=second_url).path in expected_paths


@pytest.mark.parametrize(
    argnames="months_ago",
    argvalues=[2, -1],
    ids=["too_old", "in_the_future"],
)
def test_month_out_of_range(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabase,
    months_ago: int,
) -> None:
    """Only the current and the previous month can be requested."""
    response = request_reco_counts_report(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        database_id=vuforia_database.database_id,
        month=month_offset_from_now(months=-months_ago),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    response_json = json.loads(s=response.text)
    assert response_json["result_code"] == ResultCodes.FAIL.value


@pytest.mark.parametrize(
    argnames="month",
    argvalues=["2020", "2020-1", "January", "2020-01-01", 202001],
    ids=["year_only", "one_digit", "name", "date", "not_a_string"],
)
def test_malformed_month(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabase,
    month: str | int,
) -> None:
    """The month must be given in the ``YYYY-mm`` form."""
    response = request_reco_counts_report(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        database_id=vuforia_database.database_id,
        month=month,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    response_json = json.loads(s=response.text)
    assert response_json["result_code"] == ResultCodes.FAIL.value


def test_body_is_not_an_object(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabase,
) -> None:
    """The request body must be a JSON object."""
    response = request_reco_counts_report_json(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        database_id=vuforia_database.database_id,
        request_json=[],
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    response_json = json.loads(s=response.text)
    assert response_json["result_code"] == ResultCodes.FAIL.value


def test_unknown_database_id(
    *, base_vws_url: str, vuforia_database: CloudDatabase
) -> None:
    """The path must name the database which the request's server
    keys belong to.
    """
    response = request_reco_counts_report(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        database_id=uuid.uuid4().hex,
        month=month_offset_from_now(months=0),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    response_json = json.loads(s=response.text)
    assert (
        response_json["result_code"]
        == ResultCodes.AUTHENTICATION_FAILURE.value
    )


def test_database_name_in_path(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabase,
) -> None:
    """A database is named in the path by its ID, not by its name."""
    response = request_reco_counts_report(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        database_id=vuforia_database.database_name,
        month=month_offset_from_now(months=0),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    response_json = json.loads(s=response.text)
    assert (
        response_json["result_code"]
        == ResultCodes.AUTHENTICATION_FAILURE.value
    )
