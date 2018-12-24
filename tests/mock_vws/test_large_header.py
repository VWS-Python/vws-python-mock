"""
Tests for XXX.
"""

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


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestIncorrect:
    """
    XXX
    """

    def test_not_integer(self, endpoint: Endpoint) -> None:
        """
        XXX
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        max_header_length = 8333
        headers = {**endpoint_headers, 'extra_key': ''}
        header_length = len(str(headers))
        header_length_to_add = max_header_length - header_length
        extra_key_value = header_length_to_add * '0'
        headers['extra_key'] = 'a' * header_length_to_add
        # 8183 not too large
        # 8184 too large

        # Max header length = 8333
        # headers = {**endpoint_headers, 'extra': 'a' * 8184}
        print(len(str(headers)))
        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )

        assert response.status_code == endpoint.successful_headers_status_code

# TODO also send cookie too large
