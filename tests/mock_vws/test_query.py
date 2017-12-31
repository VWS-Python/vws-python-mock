"""
Tests for the mock of the query endpoint.

https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query.
"""

import io
from urllib.parse import urljoin

import pytest
import requests
from requests import codes
from requests_mock import POST
from urllib3.filepost import encode_multipart_formdata

from tests.mock_vws.utils import (
    VuforiaDatabaseKeys,
    authorization_header,
    rfc_1123_date,
)

def assert_success(response: Response) -> None:
    """
    Assert that the given response is a success response for performing an
    image recognition query.

    Raises:
        AssertionError: The given response is not a valid success response
            for performing an image recognition query.
    """
    assert response.status_code == codes.OK
    assert response.json().keys() == {'result_code', 'results', 'query_id'}

    query_id = response.json()['query_id']
    assert len(query_id) == 32
    assert all(char in hexdigits for char in query_id)

    assert response.json()['result_code'] == 'Success'

@pytest.mark.usefixtures('verify_mock_vuforia')
class TestQuery:
    """
    Tests for the query endpoint.
    """

    def test_no_results(
        self,
        vuforia_database_keys: VuforiaDatabaseKeys,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        With no results
        """
        image_content = high_quality_image.read()
        date = rfc_1123_date()
        request_path = '/v1/query'
        url = urljoin('https://cloudreco.vuforia.com', request_path)
        files = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        encoded_data, content_type_header = encode_multipart_formdata(files)

        authorization_string = authorization_header(
            access_key=vuforia_database_keys.client_access_key,
            secret_key=vuforia_database_keys.client_secret_key,
            method=POST,
            content=encoded_data,
            # Note that this is not the actual Content-Type header value sent.
            content_type='multipart/form-data',
            date=date,
            request_path=request_path,
        )

        headers = {
            'Authorization': authorization_string,
            'Date': date,
            'Content-Type': content_type_header,
        }

        response = requests.request(
            method=POST,
            url=url,
            headers=headers,
            data=encoded_data,
        )

        assert_success(response=response)
        assert response.json()['results'] == []
