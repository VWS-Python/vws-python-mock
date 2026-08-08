"""A fake implementation of the Vuforia reco counts report endpoints."""

import datetime
import email.utils
import json
import logging
import re
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from beartype import beartype

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump
from mock_vws._services_validators.exceptions import FailError
from mock_vws.reco_counts import RecoCountsReport

if TYPE_CHECKING:
    from mock_vws.target_manager import TargetManager

_ResponseType = tuple[int, dict[str, str], str | bytes]
_LOGGER = logging.getLogger(name=__name__)
_MONTH_PATTERN = re.compile(pattern=r"[0-9]{4}-[0-9]{2}")


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
def _months_in_range() -> set[str]:
    """Return the months which a report can be requested for.

    Only the current month and the previous month can be requested.
    """
    now = datetime.datetime.now(tz=ZoneInfo(key="UTC"))
    first_of_month = now.replace(day=1)
    last_of_previous_month = first_of_month - datetime.timedelta(days=1)
    return {
        now.strftime(format="%Y-%m"),
        last_of_previous_month.strftime(format="%Y-%m"),
    }


@beartype
def create_reco_counts_report(
    *,
    request_body: bytes,
    target_manager: TargetManager,
    generation_time_seconds: float,
    base_url: str,
) -> _ResponseType:
    """Request a reco counts report for a database.

    Args:
        request_body: The body of the request.
        target_manager: The target manager which stores generated reports.
        generation_time_seconds: The number of seconds before a generated
            report is available to download.
        base_url: The base URL to serve the generated report from.

    Returns:
        A response which includes a URL to download the report from.

    Raises:
        FailError: The given month is not a month in the ``YYYY-mm`` form
            which the report can be requested for.
    """
    request_json: dict[str, Any] = json.loads(s=request_body)
    month = request_json["month"]
    if not isinstance(month, str) or not _MONTH_PATTERN.fullmatch(
        string=month,
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

    report = RecoCountsReport(
        generation_time_seconds=generation_time_seconds,
    )
    target_manager.add_reco_counts_report(reco_counts_report=report)

    body = {
        "result_code": ResultCodes.SUCCESS.value,
        "transaction_id": uuid.uuid4().hex,
        "presigned_url": f"{base_url}/reports/recoCounts/{report.uuid_}",
    }
    body_json = json_dump(body=body)
    headers = _headers(
        content_type="application/json",
        content_length=len(body_json),
    )
    return HTTPStatus.OK, headers, body_json


@beartype
def download_reco_counts_report(
    *,
    target_manager: TargetManager,
    report_id: str,
) -> _ResponseType:
    """Download a generated reco counts report.

    Args:
        target_manager: The target manager which stores generated reports.
        report_id: The identifier of the report to download.

    Returns:
        The CSV content of the report, or a 404 response while the report is
        not ready.
    """
    report = target_manager.reco_counts_reports.get(report_id)
    if report is None or not report.is_available:
        return (
            HTTPStatus.NOT_FOUND,
            _download_headers(content_type="text/plain", content_length=0),
            "",
        )

    body = report.csv_content
    headers = _download_headers(
        content_type="text/csv",
        content_length=len(body),
    )
    return HTTPStatus.OK, headers, body
