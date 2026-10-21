"""Tests for downloading a generated reco counts report.

The endpoint is unavailable to the real-Vuforia test account, so these
run against the mocks only.
"""

import datetime as dt
import re
import time
from http import HTTPStatus
from urllib.parse import urlsplit, urlunsplit

import requests

from mock_vws.database import CloudDatabase
from tests.mock_vws.reco_counts_report.helpers import (
    AMZ_DATE_FORMAT,
    CSV_HEADER,
    CSV_ROW_PATTERN,
    REQUEST_IDS_PATTERN,
    S3_TIME_FORMAT,
    URL_EXPIRY_SECONDS,
    XML_DECLARATION,
    get_presigned_url,
    month_offset_from_now,
    utc_now,
    wait_for_report,
    with_query,
)


def test_download_report(
    *, base_vws_url: str, vuforia_database: CloudDatabase
) -> None:
    """The report is available from the given URL once it is ready.

    Until then the URL gives the response which storage gives for a
    missing object.
    """
    presigned_url = get_presigned_url(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        month=month_offset_from_now(months=0),
    )

    ready_response = wait_for_report(presigned_url=presigned_url)

    assert ready_response.status_code == HTTPStatus.OK
    assert ready_response.headers["Content-Type"] == "text/plain"
    # A real database may have recognitions this month.
    assert ready_response.text.startswith(CSV_HEADER)
    rows = ready_response.text.removeprefix(CSV_HEADER)
    assert (
        re.fullmatch(
            pattern=f"({CSV_ROW_PATTERN.pattern})*",
            string=rows,
        )
        is not None
    ), rows


def test_second_request_serves_first_report(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabase,
) -> None:
    """A second request in the same hour serves the report which the
    first request generated, without generating it again.
    """
    month = month_offset_from_now(months=0)
    first_url = get_presigned_url(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        month=month,
    )
    first_response = wait_for_report(presigned_url=first_url)
    second_url = get_presigned_url(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        month=month,
    )
    second_response = requests.get(url=second_url, timeout=30)

    # If the requests straddled an hour boundary, the second one names a
    # new file, and nothing is claimed about that.
    same_file = urlsplit(url=first_url).path == urlsplit(url=second_url).path
    assert not same_file or (
        second_response.status_code == HTTPStatus.OK
        and second_response.text == first_response.text
    )


def test_expired_url(
    *, base_vws_url: str, vuforia_database: CloudDatabase
) -> None:
    """A URL which has expired gives a 403 response.

    Storage checks the expiry before the signature, so a URL whose
    ``X-Amz-Date`` has been moved back gives the same response as a URL
    which has expired, even against real Vuforia.
    """
    presigned_url = get_presigned_url(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        month=month_offset_from_now(months=0),
    )
    signed_at = utc_now().replace(microsecond=0) - dt.timedelta(
        days=8,
    )
    expired_url = with_query(
        url=presigned_url,
        changes={
            "X-Amz-Date": signed_at.strftime(format=AMZ_DATE_FORMAT),
        },
    )

    response = requests.get(url=expired_url, timeout=30)

    expires_at = signed_at + dt.timedelta(
        seconds=URL_EXPIRY_SECONDS,
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.headers["Content-Type"] == "application/xml"
    expected_pattern = re.escape(
        pattern=(
            f"{XML_DECLARATION}<Error><Code>AccessDenied</Code>"
            "<Message>Request has expired</Message>"
            f"<X-Amz-Expires>{URL_EXPIRY_SECONDS}</X-Amz-Expires>"
            f"<Expires>{expires_at.strftime(format=S3_TIME_FORMAT)}"
            "</Expires>"
        ),
    )
    server_time_pattern = (
        r"<ServerTime>[0-9]{4}-[0-9]{2}-[0-9]{2}T"
        r"[0-9]{2}:[0-9]{2}:[0-9]{2}Z</ServerTime>"
    )
    assert (
        re.fullmatch(
            pattern=(
                expected_pattern
                + server_time_pattern
                + REQUEST_IDS_PATTERN
                + "</Error>"
            ),
            string=response.text,
        )
        is not None
    ), response.text


def test_shortened_expiry(
    *, base_vws_url: str, vuforia_database: CloudDatabase
) -> None:
    """The URL expires ``X-Amz-Expires`` seconds after its
    ``X-Amz-Date``, so shortening that puts it out of date.
    """
    presigned_url = get_presigned_url(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        month=month_offset_from_now(months=0),
    )
    short_lived_url = with_query(
        url=presigned_url,
        changes={"X-Amz-Expires": "1"},
    )
    time.sleep(2)

    response = requests.get(url=short_lived_url, timeout=30)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "<Message>Request has expired</Message>" in response.text
    assert "<X-Amz-Expires>1</X-Amz-Expires>" in response.text


def test_missing_query(
    *, base_vws_url: str, vuforia_database: CloudDatabase
) -> None:
    """The query parameters of the URL are its authorization, so the
    path
    alone is refused.
    """
    presigned_url = get_presigned_url(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        month=month_offset_from_now(months=0),
    )
    unsigned_url = urlunsplit(
        components=urlsplit(url=presigned_url)._replace(query=""),
    )

    response = requests.get(url=unsigned_url, timeout=30)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.headers["Content-Type"] == "application/xml"
    expected_pattern = re.escape(
        pattern=(
            f"{XML_DECLARATION}<Error><Code>AccessDenied</Code>"
            "<Message>Access Denied</Message>"
        ),
    )
    assert (
        re.fullmatch(
            pattern=expected_pattern + REQUEST_IDS_PATTERN + "</Error>",
            string=response.text,
        )
        is not None
    ), response.text
