"""Tests for the mock of the reco counts report endpoint."""

import datetime
import io
import json
import re
import time
import uuid
from http import HTTPMethod, HTTPStatus
from string import hexdigits
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import pytest
import requests
from beartype import beartype
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)
from vws import VWS
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import CloudDatabase
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.utils.cloud_databases import add_cloud_database
from tests.mock_vws.utils.recognition_counts import seed_recognition_counts

_VWS_HOST = "https://vws.vuforia.com"
# The recognition counts which the seeded tests set on a target.
_CURRENT_MONTH_RECOS = 3
_PREVIOUS_MONTH_RECOS = 5
_TOTAL_RECOS = 8
# The number of seconds after signing that a real presigned URL expires.
_URL_EXPIRY_SECONDS = 604799
# The form of the ``X-Amz-Date`` query parameter of a presigned URL.
_AMZ_DATE_FORMAT = "%Y%m%dT%H%M%SZ"
# The form of the times in the error for an expired URL.
_S3_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
# The query parameters of a presigned URL, in the order they are given.
_PRESIGNED_URL_PARAMETERS = [
    "X-Amz-Security-Token",
    "X-Amz-Algorithm",
    "X-Amz-Date",
    "X-Amz-SignedHeaders",
    "X-Amz-Credential",
    "X-Amz-Expires",
    "X-Amz-Signature",
]
# The request identifiers which end every cloud storage error document.
_REQUEST_IDS_PATTERN = (
    r"<RequestId>[A-Z0-9]{16}</RequestId><HostId>[A-Za-z0-9+/]+=*</HostId>"
)
_XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'
_CSV_HEADER = "target_id,reco_count\r\n"
# A row of a report: a target ID and a count.
_CSV_ROW_PATTERN = re.compile(pattern=r"[0-9a-f]{32},[0-9]+\r\n")


@beartype
class _ReportNotReadyError(Exception):
    """A report is not ready to download."""


@beartype
def _now() -> datetime.datetime:
    """Return the current time in UTC."""
    return datetime.datetime.now(tz=ZoneInfo(key="UTC"))


@beartype
def _month_offset_from_now(*, months: int) -> str:
    """Return a month in ``YYYY-mm`` form, offset from the current
    month.
    """
    now = _now()
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


@beartype
def _presigned_url(*, vuforia_database: CloudDatabase, month: str) -> str:
    """Request a report for the given month and return its download
    URL.
    """
    response = _request_reco_counts_report(
        vuforia_database=vuforia_database,
        database_id=vuforia_database.database_id,
        month=month,
    )
    assert response.status_code == HTTPStatus.OK
    presigned_url = json.loads(s=response.text)["presigned_url"]
    assert isinstance(presigned_url, str)
    return presigned_url


@beartype
def _with_query(*, url: str, changes: dict[str, str]) -> str:
    """Return the URL with the given query parameters changed."""
    split_url = urlsplit(url=url)
    query = dict(parse_qsl(qs=split_url.query))
    query.update(changes)
    new_query = urlencode(query=query)
    return urlunsplit(components=split_url._replace(query=new_query))


@beartype
def _report_key(*, url: str) -> str:
    """Return the storage key of the report at the given URL.

    That is the path of the URL without its leading slash.
    """
    return urlsplit(url=url).path.lstrip("/")


@beartype
def _assert_not_ready(*, response: requests.Response, key: str) -> None:
    """Assert that a response says that a report does not exist.

    Real Vuforia's storage gives this until the report is generated.
    """
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.headers["Content-Type"] == "application/xml"
    expected_pattern = re.escape(
        pattern=(
            f"{_XML_DECLARATION}<Error><Code>NoSuchKey</Code>"
            "<Message>The specified key does not exist.</Message>"
            f"<Key>{key}</Key>"
        ),
    )
    assert re.fullmatch(
        pattern=expected_pattern + _REQUEST_IDS_PATTERN + "</Error>",
        string=response.text,
    ), response.text


@retry(
    wait=wait_fixed(wait=0.5),
    stop=stop_after_delay(max_delay=60),
    retry=retry_if_exception_type(exception_types=(_ReportNotReadyError,)),
    reraise=True,
)
@beartype
def _wait_for_report(*, presigned_url: str) -> requests.Response:
    """Poll a report until it is generated.

    Every response before the report is ready must be the one which
    storage gives for a missing object.

    Returns:
        The response which served the report.

    Raises:
        _ReportNotReadyError: The report is not ready yet.
    """
    response = requests.get(url=presigned_url, timeout=30)
    if response.status_code == HTTPStatus.OK:
        return response
    _assert_not_ready(response=response, key=_report_key(url=presigned_url))
    raise _ReportNotReadyError


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
    def test_presigned_url_query(*, vuforia_database: CloudDatabase) -> None:
        """The URL carries the query parameters of a presigned URL.

        It is signed for one second under seven days.
        """
        before = _now().replace(microsecond=0)
        presigned_url = _presigned_url(
            vuforia_database=vuforia_database,
            month=_month_offset_from_now(months=0),
        )
        after = _now()

        query = parse_qsl(qs=urlsplit(url=presigned_url).query)
        assert [name for name, _ in query] == _PRESIGNED_URL_PARAMETERS
        parameters = dict(query)
        assert parameters["X-Amz-Security-Token"]
        assert parameters["X-Amz-Algorithm"] == "AWS4-HMAC-SHA256"
        assert parameters["X-Amz-SignedHeaders"] == "host"
        assert parameters["X-Amz-Expires"] == str(object=_URL_EXPIRY_SECONDS)
        assert all(char in hexdigits for char in parameters["X-Amz-Signature"])
        signed_at = datetime.datetime.strptime(
            parameters["X-Amz-Date"],
            _AMZ_DATE_FORMAT,
        ).replace(tzinfo=ZoneInfo(key="UTC"))
        # Real Vuforia's clock is not the test's clock.
        clock_skew = datetime.timedelta(minutes=5)
        assert before - clock_skew <= signed_at <= after + clock_skew
        signed_date = signed_at.strftime(format="%Y%m%d")
        assert parameters["X-Amz-Credential"].endswith(
            f"/{signed_date}/us-west-1/s3/aws4_request",
        )

    @staticmethod
    def test_current_month_file_name(
        *,
        vuforia_database: CloudDatabase,
    ) -> None:
        """A report for the current month is named for the date and the
        hour.
        """
        hours_before = _now().strftime(format="%Y-%m-%d-%H")
        presigned_url = _presigned_url(
            vuforia_database=vuforia_database,
            month=_month_offset_from_now(months=0),
        )
        hours_after = _now().strftime(format="%Y-%m-%d-%H")

        database_id = vuforia_database.database_id
        expected_paths = {
            f"/reports/{database_id}/{hour}.csv"
            for hour in (hours_before, hours_after)
        }
        assert urlsplit(url=presigned_url).path in expected_paths

    @staticmethod
    def test_previous_month_file_name(
        *,
        vuforia_database: CloudDatabase,
    ) -> None:
        """A report for the previous month is named for the month."""
        month = _month_offset_from_now(months=-1)
        presigned_url = _presigned_url(
            vuforia_database=vuforia_database,
            month=month,
        )

        database_id = vuforia_database.database_id
        expected_path = f"/reports/{database_id}/{month}.csv"
        assert urlsplit(url=presigned_url).path == expected_path

    @staticmethod
    def test_same_file_in_the_same_hour(
        *,
        vuforia_database: CloudDatabase,
    ) -> None:
        """Two requests for the current month in the same hour name the
        same file.
        """
        month = _month_offset_from_now(months=0)

        def request_twice() -> tuple[str, str]:
            """Request the report twice and return both URLs."""
            return (
                _presigned_url(vuforia_database=vuforia_database, month=month),
                _presigned_url(vuforia_database=vuforia_database, month=month),
            )

        hour_before = _now().hour
        first_url, second_url = request_twice()
        if _now().hour != hour_before:
            # The requests straddled an hour boundary, so they legitimately
            # named different files.
            first_url, second_url = request_twice()

        assert urlsplit(url=first_url).path == urlsplit(url=second_url).path

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


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestDownloadReport:
    """Tests for downloading a generated reco counts report.

    A real report has been observed ready within a second of being
    requested, so these run against real Vuforia as well as the mocks.
    """

    @staticmethod
    def test_download_report(*, vuforia_database: CloudDatabase) -> None:
        """The report is available from the given URL once it is ready.

        Until then the URL gives the response which storage gives for a
        missing object.
        """
        presigned_url = _presigned_url(
            vuforia_database=vuforia_database,
            month=_month_offset_from_now(months=0),
        )

        ready_response = _wait_for_report(presigned_url=presigned_url)

        assert ready_response.status_code == HTTPStatus.OK
        assert ready_response.headers["Content-Type"] == "text/plain"
        # A real database may have recognitions this month.
        assert ready_response.text.startswith(_CSV_HEADER)
        rows = ready_response.text.removeprefix(_CSV_HEADER)
        assert re.fullmatch(
            pattern=f"({_CSV_ROW_PATTERN.pattern})*",
            string=rows,
        ), rows

    @staticmethod
    def test_second_request_serves_first_report(
        *,
        vuforia_database: CloudDatabase,
    ) -> None:
        """A second request in the same hour serves the report which the
        first request generated, without generating it again.
        """
        month = _month_offset_from_now(months=0)
        first_url = _presigned_url(
            vuforia_database=vuforia_database,
            month=month,
        )
        first_response = _wait_for_report(presigned_url=first_url)
        second_url = _presigned_url(
            vuforia_database=vuforia_database,
            month=month,
        )
        if urlsplit(url=first_url).path != urlsplit(url=second_url).path:
            pytest.skip(reason="The requests straddled an hour boundary.")

        second_response = requests.get(url=second_url, timeout=30)

        assert second_response.status_code == HTTPStatus.OK
        assert second_response.text == first_response.text

    @staticmethod
    def test_expired_url(*, vuforia_database: CloudDatabase) -> None:
        """A URL which has expired gives a 403 response.

        Storage checks the expiry before the signature, so a URL whose
        ``X-Amz-Date`` has been moved back gives the same response as a URL
        which has expired, even against real Vuforia.
        """
        presigned_url = _presigned_url(
            vuforia_database=vuforia_database,
            month=_month_offset_from_now(months=0),
        )
        signed_at = _now().replace(microsecond=0) - datetime.timedelta(
            days=8,
        )
        expired_url = _with_query(
            url=presigned_url,
            changes={
                "X-Amz-Date": signed_at.strftime(format=_AMZ_DATE_FORMAT),
            },
        )

        response = requests.get(url=expired_url, timeout=30)

        expires_at = signed_at + datetime.timedelta(
            seconds=_URL_EXPIRY_SECONDS,
        )
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.headers["Content-Type"] == "application/xml"
        expected_pattern = re.escape(
            pattern=(
                f"{_XML_DECLARATION}<Error><Code>AccessDenied</Code>"
                "<Message>Request has expired</Message>"
                f"<X-Amz-Expires>{_URL_EXPIRY_SECONDS}</X-Amz-Expires>"
                f"<Expires>{expires_at.strftime(format=_S3_TIME_FORMAT)}"
                "</Expires>"
            ),
        )
        server_time_pattern = (
            r"<ServerTime>[0-9]{4}-[0-9]{2}-[0-9]{2}T"
            r"[0-9]{2}:[0-9]{2}:[0-9]{2}Z</ServerTime>"
        )
        assert re.fullmatch(
            pattern=(
                expected_pattern
                + server_time_pattern
                + _REQUEST_IDS_PATTERN
                + "</Error>"
            ),
            string=response.text,
        ), response.text

    @staticmethod
    def test_shortened_expiry(*, vuforia_database: CloudDatabase) -> None:
        """The URL expires ``X-Amz-Expires`` seconds after its
        ``X-Amz-Date``, so shortening that puts it out of date.
        """
        presigned_url = _presigned_url(
            vuforia_database=vuforia_database,
            month=_month_offset_from_now(months=0),
        )
        short_lived_url = _with_query(
            url=presigned_url,
            changes={"X-Amz-Expires": "1"},
        )
        time.sleep(2)

        response = requests.get(url=short_lived_url, timeout=30)

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert "<Message>Request has expired</Message>" in response.text
        assert "<X-Amz-Expires>1</X-Amz-Expires>" in response.text

    @staticmethod
    def test_missing_query(*, vuforia_database: CloudDatabase) -> None:
        """The query parameters of the URL are its authorization, so the
        path
        alone is refused.
        """
        presigned_url = _presigned_url(
            vuforia_database=vuforia_database,
            month=_month_offset_from_now(months=0),
        )
        unsigned_url = urlunsplit(
            components=urlsplit(url=presigned_url)._replace(query=""),
        )

        response = requests.get(url=unsigned_url, timeout=30)

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.headers["Content-Type"] == "application/xml"
        expected_pattern = re.escape(
            pattern=(
                f"{_XML_DECLARATION}<Error><Code>AccessDenied</Code>"
                "<Message>Access Denied</Message>"
            ),
        )
        assert re.fullmatch(
            pattern=expected_pattern + _REQUEST_IDS_PATTERN + "</Error>",
            string=response.text,
        ), response.text


@pytest.fixture(name="fresh_database")
def fixture_fresh_database(
    *,
    mock_only_vuforia: VuforiaBackend,
) -> CloudDatabase:
    """A database which no report has been requested for.

    The shared test database is one database for the whole test run, so a
    backend whose report store outlives a test serves the report which an
    earlier test generated for it, as real Vuforia does with the shared
    real database.
    Tests which need a report which they generated themselves use their own
    database.
    """
    database = CloudDatabase()
    add_cloud_database(backend=mock_only_vuforia, cloud_database=database)
    return database


@beartype
def _vws_client(*, database: CloudDatabase) -> VWS:
    """Return a client for the given database."""
    return VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )


@pytest.mark.usefixtures("mock_only_vuforia")
class TestDownloadReportMockOnly:
    """Tests for downloading a report which cannot run against real
    Vuforia.

    Nothing sets recognition counts on real Vuforia, the mock's generation
    time is known where real Vuforia's is not, and only real Vuforia can sign
    a URL for its storage.
    """

    @staticmethod
    def test_not_ready(*, fresh_database: CloudDatabase) -> None:
        """Until the report is generated, the URL gives the response which
        storage gives for a missing object.
        """
        presigned_url = _presigned_url(
            vuforia_database=fresh_database,
            month=_month_offset_from_now(months=0),
        )

        response = requests.get(url=presigned_url, timeout=30)

        _assert_not_ready(
            response=response,
            key=_report_key(url=presigned_url),
        )

    @staticmethod
    def test_unknown_report(*, vuforia_database: CloudDatabase) -> None:
        """A file which no request generated gives the response which
        storage gives for a missing object.

        Real Vuforia refuses such a URL because its signature does not match
        the file, and the mock does not check signatures.
        """
        presigned_url = _presigned_url(
            vuforia_database=vuforia_database,
            month=_month_offset_from_now(months=0),
        )
        split_url = urlsplit(url=presigned_url)
        database_id = vuforia_database.database_id
        unknown_path = f"/reports/{database_id}/1999-01.csv"
        unknown_url = urlunsplit(
            components=split_url._replace(path=unknown_path),
        )

        response = requests.get(url=unknown_url, timeout=30)

        _assert_not_ready(response=response, key=unknown_path.lstrip("/"))

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
        fresh_database: CloudDatabase,
        high_quality_image: io.BytesIO,
        image_file_failed_state: io.BytesIO,
        months_ago: int,
        expected_reco_count: int,
    ) -> None:
        """The report has a row for each target recognized in the
        month.
        """
        vws_client = _vws_client(database=fresh_database)
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
            current_month_recos=_CURRENT_MONTH_RECOS,
            previous_month_recos=_PREVIOUS_MONTH_RECOS,
            total_recos=_TOTAL_RECOS,
        )
        presigned_url = _presigned_url(
            vuforia_database=fresh_database,
            month=_month_offset_from_now(months=-months_ago),
        )

        ready_response = _wait_for_report(presigned_url=presigned_url)

        assert ready_response.text == (
            f"{_CSV_HEADER}{recognized_target_id},{expected_reco_count}\r\n"
        )
        assert unrecognized_target_id not in ready_response.text

    @staticmethod
    def test_counts_set_after_first_request(
        *,
        mock_only_vuforia: VuforiaBackend,
        fresh_database: CloudDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """A second request in the same hour does not generate the report
        again, so counts set between the two requests are not in it.
        """
        vws_client = _vws_client(database=fresh_database)
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        month = _month_offset_from_now(months=0)
        first_url = _presigned_url(
            vuforia_database=fresh_database,
            month=month,
        )
        seed_recognition_counts(
            backend=mock_only_vuforia,
            vuforia_database=fresh_database,
            target_id=target_id,
            current_month_recos=_CURRENT_MONTH_RECOS,
            previous_month_recos=_PREVIOUS_MONTH_RECOS,
            total_recos=_TOTAL_RECOS,
        )
        second_url = _presigned_url(
            vuforia_database=fresh_database,
            month=month,
        )
        if urlsplit(url=first_url).path != urlsplit(url=second_url).path:
            pytest.skip(reason="The requests straddled an hour boundary.")

        ready_response = _wait_for_report(presigned_url=second_url)

        assert ready_response.text == _CSV_HEADER
