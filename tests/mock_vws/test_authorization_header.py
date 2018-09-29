"""
Tests for the `Authorization` header.
"""

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
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import get_vws_target, query
import uuid
import io


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

    @pytest.mark.parametrize('authorization_string', [
        'gibberish',
        'VWS',
        'VWS ',
    ])
    def test_one_part(
        self,
        endpoint: Endpoint,
        authorization_string: str,
    ) -> None:
        """
        XXX
        """
        date = rfc_1123_date()

        headers: Dict[str, Union[str, bytes]] = {
            **endpoint.prepared_request.headers,
            'Authorization': authorization_string,
            'Date': date,
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

    @pytest.mark.parametrize('authorization_string', [
        'VWS foobar:',
        'VWS foobar',
    ])
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
            'Authorization': authorization_string,
            'Date': date,
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
            # TODO
            # assert response.text == 'Malformed authorization header.'
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
        vuforia_database_keys: VuforiaDatabase,
    ) -> None:
        """
        If the server access key given does not match any database, a
        ``Fail`` response is returned.
        """
        keys = vuforia_database_keys
        keys.server_access_key = b'example'
        response = get_vws_target(
            target_id=uuid.uuid4().hex,
            vuforia_database_keys=keys,
        )

        assert_vws_failure(
            response=response,
            status_code=codes.BAD_REQUEST,
            result_code=ResultCodes.FAIL,
        )

    def test_bad_access_key_query(
        self,
        vuforia_database_keys: VuforiaDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        If the client access key given is incorrect, an
        ``UNAUTHORIZED`` response is returned.
        """
        vuforia_database_keys.client_access_key = b'example'
        image_content = high_quality_image.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(
            vuforia_database_keys=vuforia_database_keys,
            body=body,
        )

        assert_vwq_failure(
            response=response,
            status_code=codes.UNAUTHORIZED,
            content_type='application/json',
        )

    def test_bad_secret_key_services(
        self,
        vuforia_database_keys: VuforiaDatabase,
    ) -> None:
        """
        If the server secret key given is incorrect, an
        ``AuthenticationFailure`` response is returned.
        """
        keys = vuforia_database_keys
        keys.server_secret_key = b'example'
        response = get_vws_target(
            target_id=uuid.uuid4().hex,
            vuforia_database_keys=keys,
        )

        assert_vws_failure(
            response=response,
            status_code=codes.UNAUTHORIZED,
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )

    def test_bad_secret_key_query(
        self,
        vuforia_database_keys: VuforiaDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        If the client secret key given is incorrect, an
        ``UNAUTHORIZED`` response is returned.
        """
        vuforia_database_keys.client_secret_key = b'example'
        image_content = high_quality_image.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(
            vuforia_database_keys=vuforia_database_keys,
            body=body,
        )

        assert_vwq_failure(
            response=response,
            status_code=codes.UNAUTHORIZED,
            content_type='application/json',
        )
