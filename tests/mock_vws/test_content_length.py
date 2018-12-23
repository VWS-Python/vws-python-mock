"""
Tests for the ``Content-Length`` header.
"""

import pytest
import requests
from requests import codes
from requests.structures import CaseInsensitiveDict

from tests.mock_vws.utils import Endpoint


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestIncorrect:
    """
    Tests for the ``Content-Length`` header set incorrectly.

    We cannot test what happens if ``Content-Length`` is removed from a
    prepared request because ``requests-mock`` behaves differently to
    ``requests`` - https://github.com/jamielennox/requests-mock/issues/80.
    """

    def test_not_integer(self, endpoint: Endpoint) -> None:
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
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )

        assert response.text == ''
        assert response.headers == {
            'Content-Length': '0',
            'Connection': 'Close',
        }
        assert response.status_code == codes.BAD_REQUEST
