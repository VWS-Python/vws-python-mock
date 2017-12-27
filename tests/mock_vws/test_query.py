"""
Tests for the mock of the query endpoint.

https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query.
"""

import io
from typing import Any, Dict
from urllib.parse import urljoin

import pytest
import requests
from requests import codes
from requests_mock import POST

from tests.utils import VuforiaDatabaseKeys
from vws._request_utils import authorization_header, rfc_1123_date


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestQuery:
    """
    XXX
    """

    def test_no_results(
        self,
        vuforia_database_keys: VuforiaDatabaseKeys,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        XXX
        """
        content = high_quality_image.read()
        content_type = 'multipart/form-data'
        query: Dict[str, Any] = {}
        date = rfc_1123_date()
        request_path = '/v1/query'
        url = urljoin('https://cloudreco.vuforia.com', request_path)

        request = requests.Request(
            method=POST,
            url=url,
            headers={},
            data=query,
            files={
                'image': ('image.jpeg', content, 'image/jpeg'),
            }
        )

        prepared_request = request.prepare()

        authorization_string = authorization_header(
            access_key=vuforia_database_keys.client_access_key,
            secret_key=vuforia_database_keys.client_secret_key,
            method=POST,
            content=prepared_request.body,
            content_type=content_type,
            date=date,
            request_path=request_path,
        )

        headers = {
            **prepared_request.headers,
            'Authorization': authorization_string,
            'Date': date,
        }

        prepared_request.prepare_headers(headers=headers)

        session = requests.Session()
        response = session.send(request=prepared_request)
        assert response.status_code == codes.OK
