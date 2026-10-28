"""Shared helpers for reco counts report tests."""

import datetime as dt
import json
import re
from http import HTTPMethod, HTTPStatus
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

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

from vws_mock_contract_tests.fixtures.credentials import (
    CloudDatabaseCredentials,
)

CURRENT_MONTH_RECOS = 3

PREVIOUS_MONTH_RECOS = 5

TOTAL_RECOS = 8

URL_EXPIRY_SECONDS = 604799

AMZ_DATE_FORMAT = "%Y%m%dT%H%M%SZ"

S3_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

PRESIGNED_URL_PARAMETERS = [
    "X-Amz-Security-Token",
    "X-Amz-Algorithm",
    "X-Amz-Date",
    "X-Amz-SignedHeaders",
    "X-Amz-Credential",
    "X-Amz-Expires",
    "X-Amz-Signature",
]

REQUEST_IDS_PATTERN = (
    r"<RequestId>[A-Z0-9]{16}</RequestId><HostId>[A-Za-z0-9+/]+=*</HostId>"
)

XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'

CSV_HEADER = "target_id,reco_count\r\n"

CSV_ROW_PATTERN = re.compile(pattern=r"[0-9a-f]{32},[0-9]+\r\n")


@beartype
class _ReportNotReadyError(Exception):
    """A report is not ready to download."""


@beartype
def utc_now() -> dt.datetime:
    """Return the current time in UTC."""
    return dt.datetime.now(tz=ZoneInfo(key="UTC"))


@beartype
def month_offset_from_now(*, months: int) -> str:
    """Return a month in ``YYYY-mm`` form, offset from the current
    month.
    """
    now = utc_now()
    total_months = now.year * 12 + now.month - 1 + months
    year, month_index = divmod(total_months, 12)
    return f"{year:04d}-{month_index + 1:02d}"


@beartype
def request_reco_counts_report_json(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabaseCredentials,
    database_id: str,
    request_json: object,
) -> requests.Response:
    """Request a reco counts report and return the response.

    The report is requested for the database named by the given ID, and the
    request is signed with the given database's server keys.
    """
    request_path = f"/imagetargets/databases/{database_id}/reports/recoCounts"
    content_type = "application/json"
    content = json.dumps(obj=request_json).encode(encoding="utf-8")
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
        url=base_vws_url + request_path,
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
def request_reco_counts_report(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabaseCredentials,
    database_id: str,
    month: str | int,
) -> requests.Response:
    """Request a reco counts report for one month."""
    return request_reco_counts_report_json(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        database_id=database_id,
        request_json={"month": month},
    )


@beartype
def get_presigned_url(
    *,
    base_vws_url: str,
    vuforia_database: CloudDatabaseCredentials,
    month: str,
) -> str:
    """Request a report for the given month and return its download
    URL.
    """
    response = request_reco_counts_report(
        base_vws_url=base_vws_url,
        vuforia_database=vuforia_database,
        database_id=vuforia_database.database_id,
        month=month,
    )
    assert response.status_code == HTTPStatus.OK
    presigned_url: object = json.loads(s=response.text)["presigned_url"]
    assert isinstance(presigned_url, str)
    return presigned_url


@beartype
def with_query(*, url: str, changes: dict[str, str]) -> str:
    """Return the URL with the given query parameters changed."""
    split_url = urlsplit(url=url)
    query = dict(parse_qsl(qs=split_url.query))
    query.update(changes)
    new_query = urlencode(query=query)
    return urlunsplit(components=split_url._replace(query=new_query))


@beartype
def report_key(*, url: str) -> str:
    """Return the storage key of the report at the given URL.

    That is the path of the URL without its leading slash.
    """
    return urlsplit(url=url).path.lstrip("/")


@beartype
def assert_not_ready(*, response: requests.Response, key: str) -> None:
    """Assert that a response says that a report does not exist.

    Real Vuforia's storage gives this until the report is generated.
    """
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.headers["Content-Type"] == "application/xml"
    expected_pattern = re.escape(
        pattern=(
            f"{XML_DECLARATION}<Error><Code>NoSuchKey</Code>"
            "<Message>The specified key does not exist.</Message>"
            f"<Key>{key}</Key>"
        ),
    )
    assert (
        re.fullmatch(
            pattern=expected_pattern + REQUEST_IDS_PATTERN + "</Error>",
            string=response.text,
        )
        is not None
    ), response.text


@retry(
    wait=wait_fixed(wait=0.5),
    stop=stop_after_delay(max_delay=60),
    retry=retry_if_exception_type(exception_types=(_ReportNotReadyError,)),
    reraise=True,
)
@beartype
def wait_for_report(*, presigned_url: str) -> requests.Response:
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
    assert_not_ready(response=response, key=report_key(url=presigned_url))
    raise _ReportNotReadyError


@beartype
def make_vws_client(
    *, base_vws_url: str, database: CloudDatabaseCredentials
) -> VWS:
    """Return a client for the given database."""
    return VWS(
        base_vws_url=base_vws_url,
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )
