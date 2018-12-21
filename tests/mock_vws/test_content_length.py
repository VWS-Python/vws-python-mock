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
        A ``GATEWAY_TIMEOUT`` is given if the given content length is too
        large.
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        if not endpoint_headers.get('Content-Type'):
            return

        content_length = str(len(endpoint.prepared_request.body) + 1000000)
        headers = {
            **endpoint_headers,
            # This is the root cause - the content length.
            # TODO error if too big or too small
            'Content-Length': content_length,
        }

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
