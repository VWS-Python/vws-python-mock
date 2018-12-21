from datetime import datetime, timedelta

import pytest
import requests
from requests import codes

from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import assert_vws_failure
from tests.mock_vws.utils.authorization import (
    authorization_header,
    rfc_1123_date,
)


@pytest.mark.usefixtures('verify_mock_vuforia')
class Test504:
    def test_invalid_json(
        self,
        vuforia_database: VuforiaDatabase,
        endpoint: Endpoint,
    ) -> None:
        """
        Giving invalid JSON to endpoints returns error responses.
        """
        content = b'a'
        date = rfc_1123_date()

        endpoint_headers = dict(endpoint.prepared_request.headers)
        content_type = endpoint_headers.get('Content-Type', '')
        assert isinstance(content_type, str)
        endpoint_headers = dict(endpoint.prepared_request.headers)

        authorization_string = authorization_header(
            access_key=vuforia_database.server_access_key,
            secret_key=vuforia_database.server_secret_key,
            method=str(endpoint.prepared_request.method),
            content=content,
            content_type=content_type,
            date=date,
            request_path=endpoint.prepared_request.path_url,
        )

        headers = {
            **endpoint_headers,
            'Authorization': authorization_string,
            'Date': date,
            # 'Content-Type': content_type,
            # 'Content-Length': str(len(content)),
        }

        endpoint.prepared_request.prepare_body(  # type: ignore
            data=content,
            files=None,
        )

        endpoint.prepared_request.prepare_headers(  # type: ignore
            headers=headers,
        )
        session = requests.Session()
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )

        if content_type:
            assert response.text == ''
            assert response.headers == {'Content-Length': '0', 'Connection': 'keep-alive'}
            assert response.status_code == codes.GATEWAY_TIMEOUT
            return

        # This is an undocumented difference between `/summary` and other
        # endpoints.
        if endpoint.prepared_request.path_url == '/summary':
            assert_vws_failure(
                response=response,
                status_code=codes.UNAUTHORIZED,
                result_code=ResultCodes.AUTHENTICATION_FAILURE,
            )
            return

        assert response.status_code == codes.BAD_REQUEST
        assert response.text == ''
        assert 'Content-Type' not in response.headers
