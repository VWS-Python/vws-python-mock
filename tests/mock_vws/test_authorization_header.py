"""
Tests for the `Authorization` header.
"""

from pathlib import Path
from typing import Dict, Union
from urllib.parse import urlparse

import pytest
import requests
from requests import codes
from requests.structures import CaseInsensitiveDict

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import (
    assert_vwq_failure,
    assert_vws_failure,
)
from tests.mock_vws.utils.authorization import rfc_1123_date


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestAuthorizationHeader:
    """
    Tests for what happens when the `Authorization` header is not as expected.
    """

    def test_missing(self, endpoint: Endpoint) -> None:
        """
        An `UNAUTHORIZED` response is returned when no `Authorization` header
        is given.
        """
        date = rfc_1123_date()
        endpoint_headers = dict(endpoint.prepared_request.headers)

        headers: Dict[str, Union[str, bytes]] = {
            **endpoint_headers,
            'Date': date,
        }

        headers.pop('Authorization', None)

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
                content_type='text/plain; charset=ISO-8859-1',
            )
            assert response.text == 'Authorization header missing.'
            return

        assert_vws_failure(
            response=response,
            status_code=codes.UNAUTHORIZED,
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestMalformed:
    """
    Tests for passing a malformed ``Authorization`` header.
    """

    @pytest.mark.parametrize(
        'authorization_string',
        [
            b'gibberish',
            b'VWS',
            b'VWS ',
        ],
    )
    def test_one_part(
        self,
        endpoint: Endpoint,
        authorization_string: bytes,
    ) -> None:
        """
        A valid authorization string is two "parts" when split on a space. When
        a string is given which is one "part", a ``BAD_REQUEST`` or
        ``UNAUTHORIZED`` response is returned.
        """
        date = rfc_1123_date()

        headers: Dict[str, Union[str, bytes]] = {
            **endpoint.prepared_request.headers,
            'Authorization':
            authorization_string,
            'Date':
            date,
        }

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
                content_type='text/plain; charset=ISO-8859-1',
            )
            assert response.text == 'Malformed authorization header.'
            return

        assert_vws_failure(
            response=response,
            status_code=codes.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    @pytest.mark.parametrize(
        'authorization_string',
        [
            b'VWS foobar:',
            b'VWS foobar',
        ],
    )
    def test_missing_signature(
        self,
        endpoint: Endpoint,
        authorization_string: str,
    ) -> None:
        """
        If a signature is missing `Authorization` header is given, a
        ``BAD_REQUEST`` response is given.
        """
        date = rfc_1123_date()

        headers: Dict[str, Union[str, bytes]] = {
            **endpoint.prepared_request.headers,
            'Authorization':
            authorization_string,
            'Date':
            date,
        }

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
                status_code=codes.INTERNAL_SERVER_ERROR,
                content_type='text/html; charset=ISO-8859-1',
            )
            current_parent = Path(__file__).parent
            resources = current_parent / 'resources'
            known_response = resources / 'query_out_of_bounds_response'
            assert response.text == known_response.read_text()
            return

        assert_vws_failure(
            response=response,
            status_code=codes.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )
