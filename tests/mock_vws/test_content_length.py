"""
Tests for the ``Content-Length`` header.
"""

from datetime import datetime, timedelta
from urllib.parse import urlparse

import pytest
import requests
from requests import codes
from requests.structures import CaseInsensitiveDict

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
    assert_vwq_failure,
)
from tests.mock_vws.utils.authorization import (
    authorization_header,
    rfc_1123_date,
)


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestIncorrect:
    """
    XXX
    """

    def test_too_large(self, endpoint: Endpoint) -> None:
        """
        A ``GATEWAY_TIMEOUT`` is given if the given content length is too
        large.
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        if not endpoint_headers.get('Content-Type'):
            return

        content_length = str(len(endpoint.prepared_request.body) + 1)
        headers = {**endpoint_headers, 'Content-Length': content_length}

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )

        assert response.text == ''
        assert response.headers == {
            'Content-Length': '0',
            'Connection': 'keep-alive',
        }
        assert response.status_code == codes.GATEWAY_TIMEOUT

    def test_too_small(self, endpoint: Endpoint) -> None:
        """
        An ``UNAUTHORIZED`` response is given if the given content length is
        too small.
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        if not endpoint_headers.get('Content-Type'):
            return

        content_length = str(len(endpoint.prepared_request.body) - 1)
        headers = {**endpoint_headers, 'Content-Length': content_length}

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == 'cloudreco.vuforia.com':
            assert_vwq_failure(
                response=response,
                status_code=codes.UNAUTHORIZED,
                content_type='application/json',
            )
            return

        assert_vws_failure(
            response=response,
            status_code=codes.UNAUTHORIZED,
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )
