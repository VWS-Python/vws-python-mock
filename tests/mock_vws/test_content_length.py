from datetime import datetime, timedelta

import pytest
import requests
from requests import codes
from requests.structures import CaseInsensitiveDict

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import assert_vws_failure
from tests.mock_vws.utils.authorization import (
    authorization_header,
    rfc_1123_date,
)


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestIncorrect:

    def test_too_large(self, endpoint: Endpoint) -> None:
        """
        XXX
        """
        content = endpoint.prepared_request.body
        date = rfc_1123_date()

        endpoint_headers = dict(endpoint.prepared_request.headers)
        content_type = endpoint_headers.get('Content-Type', '')
        if not content_type:
            return
        assert isinstance(content_type, str)

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
            'Content-Type': content_type,
            # This is the root cause - the content length.
            # TODO error if too big or too small
            'Content-Length': str(len(content) + 1),
        }

        endpoint.prepared_request.prepare_body(  # type: ignore
            data=content,
            files=None,
        )

        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )

        assert response.text == ''
        assert response.headers == {'Content-Length': '0', 'Connection': 'keep-alive'}
        assert response.status_code == codes.GATEWAY_TIMEOUT
