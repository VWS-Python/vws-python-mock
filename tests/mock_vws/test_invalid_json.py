"""
Tests for giving invalid JSON to endpoints.
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
    assert_valid_date_header,
    assert_valid_transaction_id,
    assert_vwq_failure,
    assert_vws_failure,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors

if TYPE_CHECKING:
    from tests.mock_vws.utils import Endpoint


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInvalidJSON:
    """
    Tests for giving invalid JSON to endpoints.
    """

    @staticmethod
    def test_invalid_json(endpoint: Endpoint) -> None:
        """
        Giving invalid JSON to endpoints returns error responses.
        """
        content = b"a"
        gmt = ZoneInfo("GMT")
        now = datetime.now(tz=gmt)
        time_to_freeze = now
        with freeze_time(time_to_freeze):
            date = rfc_1123_date()

        endpoint_headers = dict(endpoint.prepared_request.headers)
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

        endpoint.prepared_request.body = content
        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        endpoint.prepared_request.prepare_content_length(body=content)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        takes_json_data = (
            endpoint.auth_header_content_type == "application/json"
        )

        assert_valid_date_header(response=response)

        if takes_json_data:
            assert_vws_failure(
                response=response,
                status_code=HTTPStatus.BAD_REQUEST,
                result_code=ResultCodes.FAIL,
            )
            return

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert_vwq_failure(
                response=response,
                status_code=HTTPStatus.BAD_REQUEST,
                content_type="application/json",
                cache_control=None,
                www_authenticate=None,
                connection="keep-alive",
            )
            expected_text = "No image."
            assert response.text == expected_text
            return

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert not response.text
        assert "Content-Type" not in response.headers

    @staticmethod
    def test_invalid_json_with_skewed_time(endpoint: Endpoint) -> None:
        """
        Giving invalid JSON to endpoints returns error responses.
        """
        # We use a skew of 70 because the maximum allowed skew for services is
        # 5 minutes, and for query is 65 minutes. 70 is comfortably larger than
        # the max of these two.
        date_skew_minutes = 70
        content = b"a"
        gmt = ZoneInfo("GMT")
        now = datetime.now(tz=gmt)
        time_to_freeze = now + timedelta(minutes=date_skew_minutes)
        with freeze_time(time_to_freeze):
            date = rfc_1123_date()

        endpoint_headers = dict(endpoint.prepared_request.headers)
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

        endpoint.prepared_request.body = content
        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        endpoint.prepared_request.prepare_content_length(body=content)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        takes_json_data = (
            endpoint.auth_header_content_type == "application/json"
        )

        assert_valid_date_header(response=response)

        if takes_json_data:
            assert_vws_failure(
                response=response,
                status_code=HTTPStatus.FORBIDDEN,
                result_code=ResultCodes.REQUEST_TIME_TOO_SKEWED,
            )
            return

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == "cloudreco.vuforia.com":
            assert response.json().keys() == {
                "transaction_id",
                "result_code",
            }
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

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert not response.text
        assert "Content-Type" not in response.headers
