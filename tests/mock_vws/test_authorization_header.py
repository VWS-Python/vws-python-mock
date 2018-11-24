"""
Tests for the `Authorization` header.
"""

import io
import uuid
from typing import Dict, Union
from urllib.parse import urlparse

import pytest
import requests
from requests import codes
from requests.structures import CaseInsensitiveDict

from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import Endpoint, get_vws_target, query
from tests.mock_vws.utils.assertions import (
    assert_valid_date_header,
    assert_valid_transaction_id,
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
            # We have seen multiple responses given.
            assert 'Powered by Jetty' in response.text
            assert '500 Server Error' in response.text
            return

        assert_vws_failure(
            response=response,
            status_code=codes.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestBadKey:
    """
    Tests for making requests with incorrect keys.
    """

    def test_bad_access_key_services(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If the server access key given does not match any database, a
        ``Fail`` response is returned.
        """
        keys = vuforia_database
        keys.server_access_key = 'example'
        response = get_vws_target(
            target_id=uuid.uuid4().hex,
            vuforia_database=keys,
        )

        assert_vws_failure(
            response=response,
            status_code=codes.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    def test_bad_access_key_query(
        self,
        vuforia_database: VuforiaDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        If the client access key given is incorrect, an
        ``UNAUTHORIZED`` response is returned.
        """
        vuforia_database.client_access_key = 'example'
        image_content = high_quality_image.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(
            vuforia_database=vuforia_database,
            body=body,
        )

        assert_vwq_failure(
            response=response,
            status_code=codes.UNAUTHORIZED,
            content_type='application/json',
        )

        assert response.json().keys() == {'transaction_id', 'result_code'}
        assert_valid_transaction_id(response=response)
        assert_valid_date_header(response=response)
        result_code = response.json()['result_code']
        transaction_id = response.json()['transaction_id']
        assert result_code == ResultCodes.AUTHENTICATION_FAILURE.value
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id":'
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )
        assert response.text == expected_text

    def test_bad_secret_key_services(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If the server secret key given is incorrect, an
        ``AuthenticationFailure`` response is returned.
        """
        keys = vuforia_database
        keys.server_secret_key = 'example'
        response = get_vws_target(
            target_id=uuid.uuid4().hex,
            vuforia_database=keys,
        )

        assert_vws_failure(
            response=response,
            status_code=codes.UNAUTHORIZED,
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )

    def test_bad_secret_key_query(
        self,
        vuforia_database: VuforiaDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        If the client secret key given is incorrect, an
        ``UNAUTHORIZED`` response is returned.
        """
        vuforia_database.client_secret_key = 'example'
        image_content = high_quality_image.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(
            vuforia_database=vuforia_database,
            body=body,
        )

        assert_vwq_failure(
            response=response,
            status_code=codes.UNAUTHORIZED,
            content_type='application/json',
        )

        assert response.json().keys() == {'transaction_id', 'result_code'}
        assert_valid_transaction_id(response=response)
        assert_valid_date_header(response=response)
        result_code = response.json()['result_code']
        transaction_id = response.json()['transaction_id']
        assert result_code == ResultCodes.AUTHENTICATION_FAILURE.value
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id":'
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )
        assert response.text == expected_text
