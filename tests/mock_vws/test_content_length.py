"""
Tests for the ``Content-Length`` header.
"""

from http import HTTPStatus
from urllib.parse import urlparse

import pytest
import requests
from requests.structures import CaseInsensitiveDict

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_valid_date_header,
    assert_vwq_failure,
    assert_vws_failure,
)


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestIncorrect:
    """
    Tests for the ``Content-Length`` header set incorrectly.

    We cannot test what happens if ``Content-Length`` is removed from a
    prepared request because ``requests-mock`` behaves differently to
    ``requests`` - https://github.com/jamielennox/requests-mock/issues/80.
    """

    @staticmethod
    def test_not_integer(endpoint: Endpoint) -> None:
        """
        A ``BAD_REQUEST`` error is given when the given ``Content-Length`` is
        not an integer.
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        if not endpoint_headers.get('Content-Type'):
            return

        content_length = '0.4'
        headers = {**endpoint_headers, 'Content-Length': content_length}
        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        assert response.status_code == HTTPStatus.BAD_REQUEST

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == 'cloudreco.vuforia.com':
            assert response.text == ''
            assert dict(response.headers) == {
                'Content-Length': str(len(response.text)),
                'Connection': 'Close',
            }
            return

        assert_valid_date_header(response=response)
        assert response.text == 'Bad Request'
        assert dict(response.headers) == {
            'content-length': str(len(response.text)),
            'content-type': 'text/plain',
            'connection': 'close',
            'server': 'envoy',
            'date': response.headers['date'],
        }

    @staticmethod
    def test_too_large(endpoint: Endpoint) -> None:
        """
        An error is given if the given content length is too large.
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        if not endpoint_headers.get('Content-Type'):
            return

        content_length = str(int(endpoint_headers['Content-Length']) + 1)
        headers = {**endpoint_headers, 'Content-Length': content_length}

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == 'cloudreco.vuforia.com':
            assert response.status_code == HTTPStatus.GATEWAY_TIMEOUT
            assert response.text == ''
            assert dict(response.headers) == {
                'Content-Length': str(len(response.text)),
                'Connection': 'keep-alive',
            }
            return

        assert_valid_date_header(response=response)
        assert response.text == 'stream timeout'
        assert dict(response.headers) == {
            'content-length': str(len(response.text)),
            'connection': 'close',
            'content-type': 'text/plain',
            'connection': 'close',
            'server': 'envoy',
            'date': response.headers['date'],
            'x-aws-region': 'eu-west-1',
        }
        assert response.status_code == HTTPStatus.REQUEST_TIMEOUT

    @staticmethod
    def test_too_small(endpoint: Endpoint) -> None:
        """
        An ``UNAUTHORIZED`` response is given if the given content length is
        too small.
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        if not endpoint_headers.get('Content-Type'):
            return

        content_length = str(int(endpoint_headers['Content-Length']) - 1)
        headers = {**endpoint_headers, 'Content-Length': content_length}

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)

        url = str(endpoint.prepared_request.url)
        netloc = urlparse(url).netloc
        if netloc == 'cloudreco.vuforia.com':
            assert_vwq_failure(
                response=response,
                status_code=HTTPStatus.UNAUTHORIZED,
                content_type='application/json',
                cache_control=None,
                www_authenticate='VWS',
                connection='keep-alive',
            )
            return

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )
