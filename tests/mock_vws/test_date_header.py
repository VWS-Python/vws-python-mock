"""
Tests for the `Date` header.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pytest
import requests
from freezegun import freeze_time
from mock_vws._constants import ResultCodes
from requests.structures import CaseInsensitiveDict
from vws_auth_tools import authorization_header, rfc_1123_date

from tests.mock_vws.utils.assertions import (
    assert_query_success,
    assert_valid_transaction_id,
    assert_vwq_failure,
    assert_vws_failure,
    assert_vws_response,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors

if TYPE_CHECKING:
    from tests.mock_vws.utils import Endpoint

_VWS_MAX_TIME_SKEW = timedelta(minutes=5)
_VWQ_MAX_TIME_SKEW = timedelta(minutes=65)
_LEEWAY = timedelta(seconds=10)


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestMissing:
    """
    Tests for what happens when the `Date` header is missing.
    """

    @staticmethod
    def test_no_date_header(endpoint: Endpoint) -> None:
        """
        A `BAD_REQUEST` response is returned when no `Date` header is given.
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        content = endpoint.prepared_request.body or b""
        assert isinstance(content, bytes)

        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=str(endpoint.prepared_request.method),
            content=content,
            content_type=endpoint.auth_header_content_type,
            date="",
            request_path=endpoint.prepared_request.path_url,
        )

        headers: dict[str, str] = endpoint_headers | {
            "Authorization": authorization_string,
        }
        headers.pop("Date", None)
        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc

        if netloc == "cloudreco.vuforia.com":
            expected_content_type = "text/plain;charset=iso-8859-1"
            assert response.text == "Date header required."
            assert_vwq_failure(
                response=response,
                status_code=HTTPStatus.BAD_REQUEST,
                content_type=expected_content_type,
                cache_control=None,
                www_authenticate=None,
                connection="keep-alive",
            )
            return

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestFormat:
    """
    Tests for what happens when the `Date` header is not in the
    expected format.
    """

    @staticmethod
    def test_incorrect_date_format(endpoint: Endpoint) -> None:
        """
        A `BAD_REQUEST` response is returned when the date given in the date
        header is not in the expected format (RFC 1123) to VWS API.

        An `UNAUTHORIZED` response is returned to the VWQ API.
        """
        gmt = ZoneInfo("GMT")
        with freeze_time(datetime.now(tz=gmt)):
            now = datetime.now(tz=gmt)
            date_incorrect_format = now.strftime("%a %b %d %H:%M:%S")

        endpoint_headers = dict(endpoint.prepared_request.headers)
        content = endpoint.prepared_request.body or b""
        assert isinstance(content, bytes)

        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=str(endpoint.prepared_request.method),
            content=content,
            content_type=endpoint.auth_header_content_type,
            date=date_incorrect_format,
            request_path=endpoint.prepared_request.path_url,
        )

        headers: dict[str, str] = endpoint_headers | {
            "Authorization": authorization_string,
            "Date": date_incorrect_format,
        }

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert response.text == "Malformed date header."
            assert_vwq_failure(
                response=response,
                status_code=HTTPStatus.UNAUTHORIZED,
                content_type="text/plain;charset=iso-8859-1",
                cache_control=None,
                www_authenticate="KWS",
                connection="keep-alive",
            )
            return

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestSkewedTime:
    """
    Tests for what happens when the `Date` header is given with an
    unexpected time.
    """

    @staticmethod
    @pytest.mark.parametrize(
        "time_multiplier",
        [1, -1],
        ids=(["After", "Before"]),
    )
    def test_date_out_of_range(
        time_multiplier: int,
        endpoint: Endpoint,
    ) -> None:
        """
        If the date header is more than five minutes (target API) or 65 minutes
        (query API) before or after the request is sent, a `FORBIDDEN` response
        is returned.

        Because there is a small delay in sending requests and Vuforia isn't
        consistent, some leeway is given.
        """
        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        skew = {
            "vws.vuforia.com": _VWS_MAX_TIME_SKEW,
            "cloudreco.vuforia.com": _VWQ_MAX_TIME_SKEW,
        }[netloc]
        time_difference_from_now = skew + _LEEWAY
        time_difference_from_now *= time_multiplier
        gmt = ZoneInfo("GMT")
        with freeze_time(datetime.now(tz=gmt) + time_difference_from_now):
            date = rfc_1123_date()

        endpoint_headers = dict(endpoint.prepared_request.headers)
        content = endpoint.prepared_request.body or b""
        assert isinstance(content, bytes)

        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=str(endpoint.prepared_request.method),
            content=content,
            content_type=endpoint.auth_header_content_type,
            date=date,
            request_path=endpoint.prepared_request.path_url,
        )

        headers = endpoint_headers | {
            "Authorization": authorization_string,
            "Date": date,
        }

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        # Even with the query endpoint, we get a JSON response.
        if netloc == "cloudreco.vuforia.com":
            assert response.json().keys() == {"transaction_id", "result_code"}
            assert response.json()["result_code"] == "RequestTimeTooSkewed"
            assert_valid_transaction_id(response=response)
            assert_vwq_failure(
                response=response,
                status_code=HTTPStatus.FORBIDDEN,
                content_type="application/json",
                cache_control=None,
                www_authenticate=None,
                connection="keep-alive",
            )
            return

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.REQUEST_TIME_TOO_SKEWED,
        )

    @staticmethod
    @pytest.mark.parametrize(
        "time_multiplier",
        [1, -1],
        ids=(["After", "Before"]),
    )
    def test_date_in_range(
        time_multiplier: int,
        endpoint: Endpoint,
    ) -> None:
        """
        If a date header is within five minutes before or after the request
        is sent, no error is returned.

        Because there is a small delay in sending requests and Vuforia isn't
        consistent, some leeway is given.
        """
        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        skew = {
            "vws.vuforia.com": _VWS_MAX_TIME_SKEW,
            "cloudreco.vuforia.com": _VWQ_MAX_TIME_SKEW,
        }[netloc]
        time_difference_from_now = skew - _LEEWAY
        time_difference_from_now *= time_multiplier
        gmt = ZoneInfo("GMT")
        with freeze_time(datetime.now(tz=gmt) + time_difference_from_now):
            date = rfc_1123_date()

        endpoint_headers = dict(endpoint.prepared_request.headers)
        content = endpoint.prepared_request.body or b""
        assert isinstance(content, bytes)

        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=str(endpoint.prepared_request.method),
            content=content,
            content_type=endpoint.auth_header_content_type,
            date=date,
            request_path=endpoint.prepared_request.path_url,
        )

        headers: dict[str, str] = endpoint_headers | {
            "Authorization": authorization_string,
            "Date": date,
        }

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert_query_success(response=response)
            return

        assert_vws_response(
            response=response,
            status_code=endpoint.successful_headers_status_code,
            result_code=endpoint.successful_headers_result_code,
        )
