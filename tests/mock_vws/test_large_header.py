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

    _MAX_HEADER_LENGTH = 8332

    def _response_for_request_with_given_header_length(
        header_length: int,
    ) -> Response:
        """
        XXX
        """
        endpoint_headers = dict(endpoint.prepared_request.headers)
        headers = {**endpoint_headers, 'extra_key': ''}
        assert header_length >= len(str(headers))
        header_length_to_add = max_header_length - len(str(headers))
        headers['extra_key'] = '0' * header_length_to_add
        endpoint.prepared_request.headers = CaseInsensitiveDict(data=headers)
        session = requests.Session()
        response = session.send(  # type: ignore
            request=endpoint.prepared_request,
        )
        return response

    def test_maximum(self, endpoint: Endpoint) -> None:
        response = _response_for_request_with_given_header_length(
            header_length=self._MAX_HEADER_LENGTH,
        )
        assert response.status_code == endpoint.successful_headers_status_code

    def test_too_large(self, endpoint: Endpoint) -> None:
        """
        XXX
        """
        response = _response_for_request_with_given_header_length(
            header_length=_MAX_HEADER_LENGTH + 1,
        )

        assert response.status_code == endpoint.successful_headers_status_code

# TODO also send cookie too large
