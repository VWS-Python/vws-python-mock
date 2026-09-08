"""A fake implementation of the Vuforia reco counts report endpoints."""

import base64
import datetime
import email.utils
import json
import logging
import re
import secrets
import string
import uuid
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Protocol, runtime_checkable
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

from beartype import beartype

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump
from mock_vws._services_validators.exceptions import FailError
from mock_vws.database import CloudDatabase
from mock_vws.reco_counts import RecoCountsReport

_ResponseType = tuple[int, dict[str, str], str | bytes]
_LOGGER = logging.getLogger(name=__name__)
_MONTH_PATTERN = re.compile(pattern=r"[0-9]{4}-[0-9]{2}")
# The form of the ``X-Amz-Date`` query parameter of a presigned URL.
_AMZ_DATE_FORMAT = "%Y%m%dT%H%M%SZ"
# The form of the times in the error which cloud storage gives for an
# expired presigned URL.
_S3_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
# Real Vuforia's presigned URLs expire one second under seven days after
# they are signed.
_URL_EXPIRY_SECONDS = 604799
# Real Vuforia signs its presigned URLs for this region.
_SIGNING_REGION = "us-west-1"


@runtime_checkable
class RecoCountsReportStore(Protocol):
    """Storage for generated reco counts reports."""

    @property
    def reco_counts_reports(self) -> dict[str, RecoCountsReport]:
        """All reco counts reports, keyed by report file path."""
        # We disable a pylint warning here because the ellipsis is required
        # for pyright to recognize this as a protocol.
        ...  # pylint: disable=unnecessary-ellipsis

    def add_reco_counts_report(
        self,
        reco_counts_report: RecoCountsReport,
    ) -> None:
        """Add a reco counts report."""
        # We disable a pylint warning here because the ellipsis is required
        # for pyright to recognize this as a protocol.
        ...  # pylint: disable=unnecessary-ellipsis


@beartype
def _now() -> datetime.datetime:
    """Return the current time in UTC."""
    return datetime.datetime.now(tz=ZoneInfo(key="UTC"))


@beartype
def _headers(*, content_type: str, content_length: int) -> dict[str, str]:
    """Return response headers which match other VWS endpoints."""
    date = email.utils.formatdate(timeval=None, localtime=False, usegmt=True)
    return {
        "Connection": "keep-alive",
        "Content-Length": str(object=content_length),
        "Content-Type": content_type,
        "Date": date,
        "server": "envoy",
        "x-envoy-upstream-service-time": "5",
        "strict-transport-security": "max-age=31536000",
        "x-aws-region": "us-east-2, us-west-2",
        "x-content-type-options": "nosniff",
    }


@beartype
def _download_headers(
    *, content_type: str, content_length: int
) -> dict[str, str]:
    """Return response headers for a report download.

    Real Vuforia serves reports from cloud storage, so these do not match the
    headers of the VWS API.
    """
    date = email.utils.formatdate(timeval=None, localtime=False, usegmt=True)
    return {
        "Content-Length": str(object=content_length),
        "Content-Type": content_type,
        "Date": date,
    }


@beartype
def _s3_error_response(
    *,
    status_code: HTTPStatus,
    code: str,
    message: str,
    fields: Mapping[str, str],
) -> _ResponseType:
    """Return an error response in the form which cloud storage gives.

    Args:
        status_code: The status code of the response.
        code: The error code, such as ``NoSuchKey``.
        message: The human-readable message of the error.
        fields: Extra elements to put between the message and the request
            identifiers, in order.

    Returns:
        An XML error document in the form which Amazon S3 gives.
    """
    request_id = "".join(
        secrets.choice(seq=string.ascii_uppercase + string.digits)
        for _ in range(16)
    )
    host_id = base64.b64encode(s=secrets.token_bytes(nbytes=57)).decode(
        encoding="ascii",
    )
    fields_xml = "".join(
        f"<{name}>{value}</{name}>" for name, value in fields.items()
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<Error><Code>{code}</Code><Message>{message}</Message>{fields_xml}"
        f"<RequestId>{request_id}</RequestId><HostId>{host_id}</HostId>"
        "</Error>"
    )
    headers = _download_headers(
        content_type="application/xml",
        content_length=len(body),
    )
    return status_code, headers, body


@beartype
def _current_month() -> str:
    """Return the current month in the ``YYYY-mm`` form."""
    return _now().strftime(format="%Y-%m")


@beartype
def _months_in_range() -> set[str]:
    """Return the months which a report can be requested for.

    Only the current month and the previous month can be requested.
    """
    now = _now()
    first_of_month = now.replace(day=1)
    last_of_previous_month = first_of_month - datetime.timedelta(days=1)
    return {
        _current_month(),
        last_of_previous_month.strftime(format="%Y-%m"),
    }


@beartype
def _report_file_name(*, month: str) -> str:
    """Return the name of the report file for the given month.

    Real Vuforia names a report for the current month after the current date
    and hour, and a report for the previous month after the month alone.

    Args:
        month: The month to report on, in the ``YYYY-mm`` form. This is either
            the current month or the previous month.

    Returns:
        The name of the report file, such as ``2026-08-08-21.csv`` for the
        current month or ``2026-07.csv`` for the previous month.
    """
    if month == _current_month():
        return _now().strftime(format="%Y-%m-%d-%H") + ".csv"
    return f"{month}.csv"


@beartype
def _presigned_query(*, signed_at: datetime.datetime) -> str:
    """Return the query string of a presigned URL.

    The parameters are the ones which real Vuforia's presigned URLs carry, in
    the same order.
    The credential, the security token and the signature stand in for real
    ones, and the mock does not check the signature.

    Args:
        signed_at: When the URL is signed. The URL expires
            ``X-Amz-Expires`` seconds after this.

    Returns:
        The query string, without a leading question mark.
    """
    access_key_id = "ASIA" + "".join(
        secrets.choice(seq=string.ascii_uppercase + string.digits)
        for _ in range(16)
    )
    security_token = base64.b64encode(
        s=secrets.token_bytes(nbytes=128),
    ).decode(encoding="ascii")
    signed_date = signed_at.strftime(format="%Y%m%d")
    query = {
        "X-Amz-Security-Token": security_token,
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Date": signed_at.strftime(format=_AMZ_DATE_FORMAT),
        "X-Amz-SignedHeaders": "host",
        "X-Amz-Credential": (
            f"{access_key_id}/{signed_date}/{_SIGNING_REGION}/s3/aws4_request"
        ),
        "X-Amz-Expires": str(object=_URL_EXPIRY_SECONDS),
        "X-Amz-Signature": secrets.token_hex(nbytes=32),
    }
    return urlencode(query=query)


@beartype
def _reco_counts_for_month(
    *,
    database: CloudDatabase,
    month: str,
) -> dict[str, int]:
    """Return the recognition count of each target in the given month.

    Args:
        database: The database to report on.
        month: The month to report on, in the ``YYYY-mm`` form. This is either
            the current month or the previous month.

    Returns:
        The recognition count of each target which has any recognitions in the
        given month, keyed by target ID.
    """
    is_current_month = month == _current_month()
    reco_counts = {
        target.target_id: (
            target.current_month_recos
            if is_current_month
            else target.previous_month_recos
        )
        for target in database.targets
    }
    return {
        target_id: reco_count
        for target_id, reco_count in reco_counts.items()
        if bool(reco_count)
    }


@beartype
def create_reco_counts_report(
    *,
    request_body: bytes,
    database: CloudDatabase,
    report_store: RecoCountsReportStore,
    generation_time_seconds: float,
    base_url: str,
) -> _ResponseType:
    """Request a reco counts report for a database.

    A report which has already been requested for the same file is not
    generated again: real Vuforia keeps serving the report which the first
    request generated, and a second request in the same hour names the same
    file.

    Args:
        request_body: The body of the request.
        database: The database to report on.
        report_store: The store which holds generated reports.
        generation_time_seconds: The number of seconds before a generated
            report is available to download.
        base_url: The base URL to serve the generated report from.

    Returns:
        A response which includes a URL to download the report from.

    Raises:
        FailError: The given month is not a month in the ``YYYY-mm`` form
            which the report can be requested for.
    """
    request_json: dict[str, Any] = json.loads(s=request_body)  # pyrefly: ignore [explicit-any]
    month = request_json["month"]
    if not isinstance(month, str) or not bool(
        _MONTH_PATTERN.fullmatch(
            string=month,
        )
    ):
        _LOGGER.warning(msg='The given "month" is not in the YYYY-mm form.')
        raise FailError(status_code=HTTPStatus.BAD_REQUEST)

    if month not in _months_in_range():
        _LOGGER.warning(
            msg=(
                'The given "month" is not the current month or the previous '
                "month."
            ),
        )
        raise FailError(status_code=HTTPStatus.BAD_REQUEST)

    file_name = _report_file_name(month=month)
    key = f"reports/{database.database_id}/{file_name}"
    if key not in report_store.reco_counts_reports:
        report = RecoCountsReport(
            key=key,
            generation_time_seconds=generation_time_seconds,
            reco_counts=_reco_counts_for_month(database=database, month=month),
        )
        report_store.add_reco_counts_report(reco_counts_report=report)

    query = _presigned_query(signed_at=_now())
    body = {
        "result_code": ResultCodes.SUCCESS.value,
        "transaction_id": uuid.uuid4().hex,
        "presigned_url": f"{base_url}/{key}?{query}",
    }
    body_json = json_dump(body=body)
    headers = _headers(
        content_type="application/json",
        content_length=len(body_json),
    )
    return HTTPStatus.OK, headers, body_json


@beartype
def _expiry_error(*, query: Mapping[str, list[str]]) -> _ResponseType | None:
    """Return the error for a URL whose signature is missing or expired.

    Cloud storage checks that a presigned URL is in date before it checks
    the signature or looks for the object, so this comes before either.

    Args:
        query: The parsed query string of the download request.

    Returns:
        A 403 response, or ``None`` if the URL is in date.
    """
    access_denied = _s3_error_response(
        status_code=HTTPStatus.FORBIDDEN,
        code="AccessDenied",
        message="Access Denied",
        fields={},
    )
    try:
        (date_value,) = query.get("X-Amz-Date", [])
        (expires_value,) = query.get("X-Amz-Expires", [])
        signed_at = datetime.datetime.strptime(
            date_value,
            _AMZ_DATE_FORMAT,
        ).replace(tzinfo=ZoneInfo(key="UTC"))
        expires_after = datetime.timedelta(seconds=int(expires_value))
    except ValueError:
        return access_denied

    now = _now()
    expires_at = signed_at + expires_after
    if now < expires_at:
        return None

    return _s3_error_response(
        status_code=HTTPStatus.FORBIDDEN,
        code="AccessDenied",
        message="Request has expired",
        fields={
            "X-Amz-Expires": expires_value,
            "Expires": expires_at.strftime(format=_S3_TIME_FORMAT),
            "ServerTime": now.strftime(format=_S3_TIME_FORMAT),
        },
    )


@beartype
def download_reco_counts_report(
    *,
    report_store: RecoCountsReportStore,
    request_path: str,
) -> _ResponseType:
    """Download a generated reco counts report.

    Args:
        report_store: The store which holds generated reports.
        request_path: The path of the request, with its query string, as
            given by the presigned URL.

    Returns:
        The CSV content of the report, a 403 response for a URL which is
        missing its query parameters or has expired, or a 404 response for
        a report which has not been generated.
        The error responses are the ones which cloud storage gives.
    """
    split_path = urlsplit(url=request_path)
    key = split_path.path.lstrip("/")
    query = parse_qs(qs=split_path.query)

    expiry_error = _expiry_error(query=query)
    if expiry_error is not None:
        return expiry_error

    report = report_store.reco_counts_reports.get(key)
    if report is None or not report.is_available:
        return _s3_error_response(
            status_code=HTTPStatus.NOT_FOUND,
            code="NoSuchKey",
            message="The specified key does not exist.",
            fields={"Key": key},
        )

    body = report.csv_content
    # Real Vuforia serves the report from S3 with a ``text/plain`` content
    # type, not ``text/csv``.
    headers = _download_headers(
        content_type="text/plain",
        content_length=len(body),
    )
    return HTTPStatus.OK, headers, body
