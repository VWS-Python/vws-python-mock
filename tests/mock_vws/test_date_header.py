"""Tests for the `Date` header."""

import json
from datetime import datetime, timedelta
from http import HTTPStatus
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_query_success,
    assert_valid_transaction_id,
    assert_vwq_failure,
    assert_vws_failure,
    assert_vws_response,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors

_VWS_MAX_TIME_SKEW = timedelta(minutes=5)
_VWQ_MAX_TIME_SKEW = timedelta(minutes=65)
_LEEWAY = timedelta(seconds=10)


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestMissing:
    """Tests for what happens when the `Date` header is missing."""

    @staticmethod
    def test_no_date_header(endpoint: Endpoint) -> None:
        """
        A `BAD_REQUEST` response is returned when no `Date` header is
        given.
        """
        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=endpoint.method,
            content=endpoint.data,
            content_type=endpoint.auth_header_content_type,
            date="",
            request_path=endpoint.path_url,
        )

        new_headers = {
            **endpoint.headers,
            "Authorization": authorization_string,
        }
        new_headers.pop("Date", None)

        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=new_headers,
            data=endpoint.data,
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )

        response = new_endpoint.send()

        handle_server_errors(response=response)

        netloc = urlparse(url=endpoint.base_url).netloc

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
    Tests for what happens when the `Date` header is not in the expected
    format.
    """

    @staticmethod
    def test_incorrect_date_format(endpoint: Endpoint) -> None:
        """A `BAD_REQUEST` response is returned when the date given in the
        date
        header is not in the expected format (RFC 1123) to VWS API.

        An `UNAUTHORIZED` response is returned to the VWQ API.
        """
        gmt = ZoneInfo(key="GMT")
        with freeze_time(time_to_freeze=datetime.now(tz=gmt)):
            now = datetime.now(tz=gmt)
            date_incorrect_format = now.strftime(format="%a %b %d %H:%M:%S")

        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=endpoint.method,
            content=endpoint.data,
            content_type=endpoint.auth_header_content_type,
            date=date_incorrect_format,
            request_path=endpoint.path_url,
        )

        new_headers = {
            **endpoint.headers,
            "Authorization": authorization_string,
            "Date": date_incorrect_format,
        }

        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=new_headers,
            data=endpoint.data,
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )
        response = new_endpoint.send()

        handle_server_errors(response=response)

        netloc = urlparse(url=endpoint.base_url).netloc
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
    unexpected
    time.
    """

    @staticmethod
    def test_date_out_of_range_after(endpoint: Endpoint) -> None:
        """If the date header is more than five minutes (target API) or 65
        minutes (query API) after the request is sent, a `FORBIDDEN`
        response
        is returned.

        Because there is a small delay in sending requests and Vuforia
        isn't consistent, some leeway is given.
        """
        netloc = urlparse(url=endpoint.base_url).netloc
        skew = {
            "vws.vuforia.com": _VWS_MAX_TIME_SKEW,
            "cloudreco.vuforia.com": _VWQ_MAX_TIME_SKEW,
        }[netloc]
        time_difference_from_now = skew + _LEEWAY
        gmt = ZoneInfo(key="GMT")
        with freeze_time(
            time_to_freeze=datetime.now(tz=gmt) + time_difference_from_now
        ):
            date = rfc_1123_date()

        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=endpoint.method,
            content=endpoint.data,
            content_type=endpoint.auth_header_content_type,
            date=date,
            request_path=endpoint.path_url,
        )

        new_headers = {
            **endpoint.headers,
            "Authorization": authorization_string,
            "Date": date,
        }

        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=new_headers,
            data=endpoint.data,
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )

        response = new_endpoint.send()

        handle_server_errors(response=response)

        # Even with the query endpoint, we get a JSON response.
        if netloc == "cloudreco.vuforia.com":
            response_json = json.loads(s=response.text)
            assert isinstance(response_json, dict)
            assert response_json.keys() == {"transaction_id", "result_code"}
            assert response_json["result_code"] == "RequestTimeTooSkewed"
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
    def test_date_out_of_range_before(endpoint: Endpoint) -> None:
        """If the date header is more than five minutes (target API) or 65
        minutes (query API) before the request is sent, a `FORBIDDEN`
        response
        is returned.

        Because there is a small delay in sending requests and Vuforia
        isn't consistent, some leeway is given.
        """
        netloc = urlparse(url=endpoint.base_url).netloc
        skew = {
            "vws.vuforia.com": _VWS_MAX_TIME_SKEW,
            "cloudreco.vuforia.com": _VWQ_MAX_TIME_SKEW,
        }[netloc]
        time_difference_from_now = skew + _LEEWAY
        gmt = ZoneInfo(key="GMT")
        with freeze_time(
            time_to_freeze=datetime.now(tz=gmt) - time_difference_from_now
        ):
            date = rfc_1123_date()

        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=endpoint.method,
            content=endpoint.data,
            content_type=endpoint.auth_header_content_type,
            date=date,
            request_path=endpoint.path_url,
        )

        new_headers = {
            **endpoint.headers,
            "Authorization": authorization_string,
            "Date": date,
        }

        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=new_headers,
            data=endpoint.data,
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )

        response = new_endpoint.send()

        handle_server_errors(response=response)

        # Even with the query endpoint, we get a JSON response.
        if netloc == "cloudreco.vuforia.com":
            response_json = json.loads(s=response.text)
            assert isinstance(response_json, dict)
            assert response_json.keys() == {"transaction_id", "result_code"}
            assert response_json["result_code"] == "RequestTimeTooSkewed"
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
    def test_date_in_range_after(endpoint: Endpoint) -> None:
        """If a date header is within five minutes after the request is
        sent,
        no error is returned.

        Because there is a small delay in sending requests and Vuforia
        isn't consistent, some leeway is given.
        """
        netloc = urlparse(url=endpoint.base_url).netloc
        skew = {
            "vws.vuforia.com": _VWS_MAX_TIME_SKEW,
            "cloudreco.vuforia.com": _VWQ_MAX_TIME_SKEW,
        }[netloc]
        time_difference_from_now = skew - _LEEWAY
        gmt = ZoneInfo(key="GMT")
        with freeze_time(
            time_to_freeze=datetime.now(tz=gmt) + time_difference_from_now
        ):
            date = rfc_1123_date()

        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=endpoint.method,
            content=endpoint.data,
            content_type=endpoint.auth_header_content_type,
            date=date,
            request_path=endpoint.path_url,
        )

        new_headers = {
            **endpoint.headers,
            "Authorization": authorization_string,
            "Date": date,
        }

        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=new_headers,
            data=endpoint.data,
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )

        response = new_endpoint.send()

        handle_server_errors(response=response)

        netloc = urlparse(url=endpoint.base_url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert_query_success(response=response)
            return

        assert_vws_response(
            response=response,
            status_code=endpoint.successful_headers_status_code,
            result_code=endpoint.successful_headers_result_code,
        )

    @staticmethod
    def test_date_in_range_before(endpoint: Endpoint) -> None:
        """If a date header is within five minutes before the request is
        sent,
        no error is returned.

        Because there is a small delay in sending requests and Vuforia
        isn't consistent, some leeway is given.
        """
        netloc = urlparse(url=endpoint.base_url).netloc
        skew = {
            "vws.vuforia.com": _VWS_MAX_TIME_SKEW,
            "cloudreco.vuforia.com": _VWQ_MAX_TIME_SKEW,
        }[netloc]
        time_difference_from_now = skew - _LEEWAY
        gmt = ZoneInfo(key="GMT")
        with freeze_time(
            time_to_freeze=datetime.now(tz=gmt) - time_difference_from_now
        ):
            date = rfc_1123_date()

        authorization_string = authorization_header(
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
            method=endpoint.method,
            content=endpoint.data,
            content_type=endpoint.auth_header_content_type,
            date=date,
            request_path=endpoint.path_url,
        )

        new_headers = {
            **endpoint.headers,
            "Authorization": authorization_string,
            "Date": date,
        }

        new_endpoint = Endpoint(
            base_url=endpoint.base_url,
            path_url=endpoint.path_url,
            method=endpoint.method,
            headers=new_headers,
            data=endpoint.data,
            successful_headers_result_code=endpoint.successful_headers_result_code,
            successful_headers_status_code=endpoint.successful_headers_status_code,
            access_key=endpoint.access_key,
            secret_key=endpoint.secret_key,
        )

        response = new_endpoint.send()

        handle_server_errors(response=response)

        netloc = urlparse(url=endpoint.base_url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert_query_success(response=response)
            return

        assert_vws_response(
            response=response,
            status_code=endpoint.successful_headers_status_code,
            result_code=endpoint.successful_headers_result_code,
        )
