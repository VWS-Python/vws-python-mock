"""
Tests for giving invalid JSON to endpoints.
"""

from datetime import datetime, timedelta
from http import HTTPStatus
from urllib.parse import urlparse

import pytest
import requests
from backports.zoneinfo import ZoneInfo
from freezegun import freeze_time
from requests.structures import CaseInsensitiveDict
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_valid_date_header,
    assert_vwq_failure,
    assert_vws_failure,
)


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestInvalidJSON:
    """
    Tests for giving invalid JSON to endpoints.
    """

    @pytest.mark.parametrize('date_skew_minutes', [0, 10])
    def test_invalid_json(
        self,
        endpoint: Endpoint,
        date_skew_minutes: int,
    ) -> None:
        """
        Giving invalid JSON to endpoints returns error responses.
        """
        date_is_skewed = not date_skew_minutes == 0
        content = b'a'
        gmt = ZoneInfo('GMT')
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

        headers = {
            **endpoint_headers,
            'Authorization': authorization_string,
            'Date': date,
        }

        endpoint.prepared_request.body = content
        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        endpoint.prepared_request.prepare_content_length(body=content)
        session = requests.Session()
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )

        takes_json_data = (
            endpoint.auth_header_content_type == 'application/json'
        )

        assert_valid_date_header(response=response)

        if date_is_skewed and takes_json_data:
            # On the real implementation, we get `HTTPStatus.FORBIDDEN` and
            # `REQUEST_TIME_TOO_SKEWED`.
            # See https://github.com/VWS-Python/vws-python-mock/issues/4 for
            # implementing this on them mock.
            return

        if not date_is_skewed and takes_json_data:
            assert_vws_failure(
                response=response,
                status_code=HTTPStatus.BAD_REQUEST,
                result_code=ResultCodes.FAIL,
            )
            return

        assert response.status_code == HTTPStatus.BAD_REQUEST
        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == 'cloudreco.vuforia.com':
            assert_vwq_failure(
                response=response,
                status_code=HTTPStatus.BAD_REQUEST,
                content_type='text/html;charset=UTF-8',
                cache_control=None,
                www_authenticate=None,
            )
            expected_text = (
                'java.lang.RuntimeException: RESTEASY007500: '
                'Could find no Content-Disposition header within part'
            )
            assert response.text == expected_text
            return

        assert response.text == ''
        assert 'Content-Type' not in response.headers
