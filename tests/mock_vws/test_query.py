"""
Tests for the mock of the query endpoint.

https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query.
"""

import base64
import calendar
import datetime
import io
import time
import uuid
from http import HTTPStatus
from typing import Any, Dict, Union
from urllib.parse import urljoin

import pytest
import requests
from backports.zoneinfo import ZoneInfo
from PIL import Image
from requests import Response
from requests_mock import POST
from urllib3.filepost import encode_multipart_formdata
from vws import VWS
from vws.reports import TargetStatuses
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import make_image_file
from tests.mock_vws.utils.assertions import (
    assert_query_success,
    assert_valid_date_header,
    assert_valid_transaction_id,
    assert_vwq_failure,
)

VWQ_HOST = 'https://cloudreco.vuforia.com'


def query(
    vuforia_database: VuforiaDatabase,
    body: Dict[str, Any],
) -> Response:
    """
    Make a request to the endpoint to make an image recognition query.

    Args:
        vuforia_database: The credentials to use to connect to
            Vuforia.
        body: The request body to send in ``multipart/formdata`` format.

    Returns:
        The response returned by the API.
    """
    date = rfc_1123_date()
    request_path = '/v1/query'
    content, content_type_header = encode_multipart_formdata(body)
    method = POST

    access_key = vuforia_database.client_access_key
    secret_key = vuforia_database.client_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
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

    vwq_host = 'https://cloudreco.vuforia.com'
    response = requests.request(
        method=method,
        url=urljoin(base=vwq_host, url=request_path),
        headers=headers,
        data=content,
    )

    return response


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestContentType:
    """
    Tests for the Content-Type header.
    """

    @pytest.mark.parametrize(
        'content_type',
        [
            'text/html',
            '',
        ],
    )
    def test_incorrect_no_boundary(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        content_type: str,
    ) -> None:
        """
        If a Content-Type header which is not ``multipart/form-data``, an
        ``UNSUPPORTED_MEDIA_TYPE`` response is given.
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = '/v1/query'
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        content, _ = encode_multipart_formdata(body)
        method = POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            content_type=content_type,
            date=date,
            request_path=request_path,
        )

        headers = {
            'Authorization': authorization_string,
            'Date': date,
            'Content-Type': content_type,
        }

        response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
        )

        assert response.text == ''
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            content_type=None,
        )

    def test_incorrect_with_boundary(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If a Content-Type header which is not ``multipart/form-data`` is given
        with the correct boundary, an ``UNSUPPORTED_MEDIA_TYPE`` response is
        given.
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = '/v1/query'
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        content, content_type_header = encode_multipart_formdata(body)
        method = POST

        content_type = 'text/html'

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            content_type=content_type,
            date=date,
            request_path=request_path,
        )

        _, boundary = content_type_header.split(';')

        content_type = 'text/html; ' + boundary
        headers = {
            'Authorization': authorization_string,
            'Date': date,
            'Content-Type': content_type,
        }

        response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
        )

        assert response.text == ''
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            content_type=None,
        )

    @pytest.mark.parametrize(
        'content_type',
        [
            'multipart/form-data',
            'multipart/form-data; extra',
            'multipart/form-data; extra=1',
        ],
    )
    def test_no_boundary(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        content_type: str,
    ) -> None:
        """
        If no boundary is given, a ``BAD_REQUEST`` is returned.
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = '/v1/query'
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        content, _ = encode_multipart_formdata(body)
        method = POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            # Note that this is not the actual Content-Type header value sent.
            content_type='multipart/form-data',
            date=date,
            request_path=request_path,
        )

        headers = {
            'Authorization': authorization_string,
            'Date': date,
            'Content-Type': content_type,
        }

        response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
        )

        expected_text = (
            'java.io.IOException: RESTEASY007550: '
            'Unable to get boundary for multipart'
        )
        assert response.text == expected_text
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            content_type='text/html;charset=UTF-8',
        )

    def test_bogus_boundary(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If a bogus boundary is given, a ``BAD_REQUEST`` is returned.
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = '/v1/query'
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        content, _ = encode_multipart_formdata(body)
        method = POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            # Note that this is not the actual Content-Type header value sent.
            content_type='multipart/form-data',
            date=date,
            request_path=request_path,
        )

        headers = {
            'Authorization': authorization_string,
            'Date': date,
            'Content-Type': 'multipart/form-data; boundary=example_boundary',
        }

        response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
        )

        expected_text = (
            'java.lang.RuntimeException: RESTEASY007500: '
            'Could find no Content-Disposition header within part'
        )
        assert response.text == expected_text
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            content_type='text/html;charset=UTF-8',
        )

    def test_extra_section(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If sections that are not the boundary section are given in the header,
        that is fine.
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = '/v1/query'
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        content, content_type_header = encode_multipart_formdata(body)
        method = POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            # Note that this is not the actual Content-Type header value sent.
            content_type='multipart/form-data',
            date=date,
            request_path=request_path,
        )

        headers = {
            'Authorization': authorization_string,
            'Date': date,
            'Content-Type': content_type_header + '; extra=1',
        }

        response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
        )

        assert_query_success(response=response)
        assert response.json()['results'] == []


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestSuccess:
    """
    Tests for successful calls to the query endpoint.
    """

    def test_no_results(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        When there are no matching images in the database, an empty list of
        results is returned.
        """
        image_content = high_quality_image.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert response.json()['results'] == []

    def test_match(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        If the exact image that was added is queried for, target data is shown.
        """
        image_content = high_quality_image.getvalue()
        metadata_encoded = base64.b64encode(b'example').decode('ascii')
        name = 'example_name'

        target_id = vws_client.add_target(
            name=name,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=metadata_encoded,
        )

        approximate_target_created = calendar.timegm(time.gmtime())

        vws_client.wait_for_target_processed(target_id=target_id)

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        [result] = response.json()['results']
        assert result.keys() == {'target_id', 'target_data'}
        assert result['target_id'] == target_id
        target_data = result['target_data']
        assert target_data.keys() == {
            'application_metadata',
            'name',
            'target_timestamp',
        }
        assert target_data['application_metadata'] == metadata_encoded
        assert target_data['name'] == name
        target_timestamp = target_data['target_timestamp']
        assert isinstance(target_timestamp, int)
        time_difference = abs(approximate_target_created - target_timestamp)
        assert time_difference < 5

    def test_not_base64_encoded_processable(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
        not_base64_encoded_processable: str,
    ) -> None:
        """
        Vuforia accepts some metadata strings which are not valid base64.
        When a target with such a string is matched by a query, Vuforia returns
        an interesting result:

        * If the metadata string is a length one greater than a multiple of 4,
          the last character is ignored.
        * If the metadata is two greater than a multiple of 4, the result is
          padded, then decoded, then encoded.
        * If the metadata is three greater than a multiple of 4, the result is
          padded, then decoded, then encoded.
        """
        image_content = high_quality_image.getvalue()
        name = 'example_name'

        target_id = vws_client.add_target(
            name=name,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=not_base64_encoded_processable,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        [result] = response.json()['results']
        query_metadata = result['target_data']['application_metadata']
        if len(not_base64_encoded_processable) % 4 == 1:
            expected_metadata_original = not_base64_encoded_processable[:-1]
        elif len(not_base64_encoded_processable) % 4 == 2:
            expected_metadata_original = not_base64_encoded_processable + '=='
        else:
            assert len(not_base64_encoded_processable) % 4 == 3
            expected_metadata_original = not_base64_encoded_processable + '='

        expected_metadata = base64.b64encode(
            base64.b64decode(expected_metadata_original),
        )
        assert query_metadata == expected_metadata.decode()


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestIncorrectFields:
    """
    Tests for incorrect and unexpected fields.
    """

    def test_missing_image(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If an image is not given, a ``BAD_REQUEST`` response is returned.
        """
        response = query(vuforia_database=vuforia_database, body={})

        assert response.text == 'No image.'
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            content_type='application/json',
        )

    def test_extra_fields(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If extra fields are given, a ``BAD_REQUEST`` response is returned.
        """
        image_content = high_quality_image.getvalue()
        body = {
            'image': ('image.jpeg', image_content, 'image/jpeg'),
            'extra_field': (None, 1, 'text/plain'),
        }

        response = query(vuforia_database=vuforia_database, body=body)

        assert response.text == 'Unknown parameters in the request.'
        assert_vwq_failure(
            response=response,
            content_type='application/json',
            status_code=HTTPStatus.BAD_REQUEST,
        )

    def test_missing_image_and_extra_fields(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If extra fields are given and no image field is given, a
        ``BAD_REQUEST`` response is returned.

        The extra field error takes precedence.
        """
        body = {
            'extra_field': (None, 1, 'text/plain'),
        }

        response = query(vuforia_database=vuforia_database, body=body)

        assert response.text == 'Unknown parameters in the request.'
        assert_vwq_failure(
            response=response,
            content_type='application/json',
            status_code=HTTPStatus.BAD_REQUEST,
        )


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestMaxNumResults:
    """
    Tests for the ``max_num_results`` parameter.
    """

    def test_default(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        The default ``max_num_results`` is 1.
        """
        image_content = high_quality_image.getvalue()

        target_id_1 = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        target_id_2 = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id_1)
        vws_client.wait_for_target_processed(target_id=target_id_2)

        body = {
            'image': ('image.jpeg', image_content, 'image/jpeg'),
        }

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert len(response.json()['results']) == 1

    @pytest.mark.parametrize('num_results', [1, b'1', 50])
    def test_valid_accepted(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        num_results: Union[int, bytes],
    ) -> None:
        """
        Numbers between 1 and 50 are valid inputs.

        We assert that the response is a success, but not that the maximum
        number of results is enforced.

        This is because uploading 50 images would be very slow.

        The documentation at
        https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query  # noqa: E501
        states that this must be between 1 and 10, but in practice, 50 is the
        maximum.
        """
        image_content = high_quality_image.getvalue()
        body = {
            'image': ('image.jpeg', image_content, 'image/jpeg'),
            'max_num_results': (None, num_results, 'text/plain'),
        }

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert response.json()['results'] == []

    def test_valid_works(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        A maximum of ``max_num_results`` results are returned.
        """
        image_content = high_quality_image.getvalue()
        add_and_wait_for_targets(
            image=high_quality_image,
            vws_client=vws_client,
            num_targets=3,
        )

        body = {
            'image': ('image.jpeg', image_content, 'image/jpeg'),
            'max_num_results': (None, 2, 'text/plain'),
        }

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert len(response.json()['results']) == 2

    @pytest.mark.parametrize('num_results', [-1, 0, 51])
    def test_out_of_range(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        num_results: int,
    ) -> None:
        """
        An error is returned if ``max_num_results`` is given as an integer out
        of the range (1, 50).

        The documentation at
        https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query.  # noqa: E501
        states that this must be between 1 and 10, but in practice, 50 is the
        maximum.
        """
        image_content = high_quality_image.getvalue()
        body = {
            'image': ('image.jpeg', image_content, 'image/jpeg'),
            'max_num_results': (None, num_results, 'text/plain'),
        }

        response = query(vuforia_database=vuforia_database, body=body)

        expected_text = (
            f'Integer out of range ({repr(num_results)}) in form data part '
            "'max_result'. Accepted range is from 1 to 50 (inclusive)."
        )
        assert response.text == expected_text
        assert_vwq_failure(
            response=response,
            content_type='application/json',
            status_code=HTTPStatus.BAD_REQUEST,
        )

    @pytest.mark.parametrize(
        'num_results',
        [b'0.1', b'1.1', b'a', b'2147483648'],
    )
    def test_invalid_type(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        num_results: bytes,
    ) -> None:
        """
        An error is returned if ``max_num_results`` is given as something other
        than an integer.

        Integers greater than 2147483647 are not considered integers because
        they are bigger than Java's maximum integer.
        """
        image_content = high_quality_image.getvalue()
        body = {
            'image': ('image.jpeg', image_content, 'image/jpeg'),
            'max_num_results': (None, num_results, 'text/plain'),
        }
        response = query(vuforia_database=vuforia_database, body=body)

        expected_text = (
            f"Invalid value '{num_results.decode()}' in form data part "
            "'max_result'. "
            'Expecting integer value in range from 1 to 50 (inclusive).'
        )
        assert response.text == expected_text
        assert_vwq_failure(
            response=response,
            content_type='application/json',
            status_code=HTTPStatus.BAD_REQUEST,
        )


def add_and_wait_for_targets(
    image: io.BytesIO,
    vws_client: VWS,
    num_targets: int,
) -> None:
    """
    Add targets with the given image.
    """
    target_ids = set([])
    for _ in range(num_targets):
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image,
            active_flag=True,
            application_metadata=None,
        )
        target_ids.add(target_id)

    for target_id in target_ids:
        vws_client.wait_for_target_processed(target_id=target_id)


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestIncludeTargetData:
    """
    Tests for the ``include_target_data`` parameter.
    """

    def test_default(
        self,
        high_quality_image: io.BytesIO,
        vws_client: VWS,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        The default ``include_target_data`` is 'top'.
        """
        add_and_wait_for_targets(
            image=high_quality_image,
            vws_client=vws_client,
            num_targets=2,
        )
        image_content = high_quality_image.getvalue()
        body = {
            'image': ('image.jpeg', image_content, 'image/jpeg'),
            'max_num_results': (None, 2, 'text/plain'),
        }

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        result_1, result_2 = response.json()['results']
        assert 'target_data' in result_1
        assert 'target_data' not in result_2

    @pytest.mark.parametrize('include_target_data', ['top', 'TOP'])
    def test_top(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        include_target_data: str,
        vws_client: VWS,
    ) -> None:
        """
        When ``include_target_data`` is set to "top" (case insensitive), only
        the first result includes target data.
        """
        add_and_wait_for_targets(
            image=high_quality_image,
            vws_client=vws_client,
            num_targets=2,
        )
        image_content = high_quality_image.getvalue()
        body = {
            'image': ('image.jpeg', image_content, 'image/jpeg'),
            'include_target_data': (None, include_target_data, 'text/plain'),
            'max_num_results': (None, 2, 'text/plain'),
        }

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        result_1, result_2 = response.json()['results']
        assert 'target_data' in result_1
        assert 'target_data' not in result_2

    @pytest.mark.parametrize('include_target_data', ['none', 'NONE'])
    def test_none(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        include_target_data: str,
        vws_client: VWS,
    ) -> None:
        """
        When ``include_target_data`` is set to "none" (case insensitive), no
        results include target data.
        """
        add_and_wait_for_targets(
            image=high_quality_image,
            vws_client=vws_client,
            num_targets=2,
        )
        image_content = high_quality_image.getvalue()
        body = {
            'image': ('image.jpeg', image_content, 'image/jpeg'),
            'include_target_data': (None, include_target_data, 'text/plain'),
            'max_num_results': (None, 2, 'text/plain'),
        }

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        result_1, result_2 = response.json()['results']
        assert 'target_data' not in result_1
        assert 'target_data' not in result_2

    @pytest.mark.parametrize('include_target_data', ['all', 'ALL'])
    def test_all(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        include_target_data: str,
        vws_client: VWS,
    ) -> None:
        """
        When ``include_target_data`` is set to "all" (case insensitive), all
        results include target data.
        """
        add_and_wait_for_targets(
            image=high_quality_image,
            vws_client=vws_client,
            num_targets=2,
        )
        image_content = high_quality_image.getvalue()
        body = {
            'image': ('image.jpeg', image_content, 'image/jpeg'),
            'include_target_data': (None, include_target_data, 'text/plain'),
            'max_num_results': (None, 2, 'text/plain'),
        }

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        result_1, result_2 = response.json()['results']
        assert 'target_data' in result_1
        assert 'target_data' in result_2

    @pytest.mark.parametrize('include_target_data', ['a', True, 0])
    def test_invalid_value(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        include_target_data: Any,
    ) -> None:
        """
        A ``BAD_REQUEST`` error is given when a string that is not one of
        'none', 'top' or 'all' (case insensitive).
        """
        image_content = high_quality_image.getvalue()
        body = {
            'image': ('image.jpeg', image_content, 'image/jpeg'),
            'include_target_data': (None, include_target_data, 'text/plain'),
        }
        response = query(vuforia_database=vuforia_database, body=body)

        expected_text = (
            f"Invalid value '{include_target_data}' in form data "
            "part 'include_target_data'. "
            "Expecting one of the (unquoted) string values 'all', 'none' or "
            "'top'."
        )
        assert response.text == expected_text
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            content_type='application/json',
        )


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestAcceptHeader:
    """
    Tests for the ``Accept`` header.
    """

    @pytest.mark.parametrize(
        'extra_headers',
        [
            {
                'Accept': 'application/json',
            },
            {},
        ],
    )
    def test_valid(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        extra_headers: Dict[str, str],
    ) -> None:
        """
        An ``Accept`` header can be given iff its value is "application/json".
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = '/v1/query'
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        content, content_type_header = encode_multipart_formdata(body)
        method = POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            # Note that this is not the actual Content-Type header value sent.
            content_type='multipart/form-data',
            date=date,
            request_path=request_path,
        )
        headers = {
            'Authorization': authorization_string,
            'Date': date,
            'Content-Type': content_type_header,
            **extra_headers,
        }

        response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
        )

        assert_query_success(response=response)
        assert response.json()['results'] == []

    def test_invalid(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        A NOT_ACCEPTABLE response is returned if an ``Accept`` header is given
        with a value which is not "application/json".
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = '/v1/query'
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        content, content_type_header = encode_multipart_formdata(body)
        method = POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            # Note that this is not the actual Content-Type header value sent.
            content_type='multipart/form-data',
            date=date,
            request_path=request_path,
        )

        headers = {
            'Authorization': authorization_string,
            'Date': date,
            'Content-Type': content_type_header,
            'Accept': 'text/html',
        }

        response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
        )

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.NOT_ACCEPTABLE,
            content_type=None,
        )


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestActiveFlag:
    """
    Tests for active versus inactive targets.
    """

    def test_inactive(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        Images which are not active are not matched.
        """
        image_content = high_quality_image.getvalue()
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=False,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert response.json()['results'] == []


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestBadImage:
    """
    Tests for bad images.
    """

    def test_corrupted(
        self,
        vuforia_database: VuforiaDatabase,
        corrupted_image_file: io.BytesIO,
    ) -> None:
        """
        No error is returned when a corrupted image is given.
        """
        corrupted_data = corrupted_image_file.getvalue()

        body = {'image': ('image.jpeg', corrupted_data, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert response.json()['results'] == []

    def test_not_image(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        No error is returned when a corrupted image is given.
        """
        not_image_data = b'not_image_data'

        body = {'image': ('image.jpeg', not_image_data, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content_type='application/json',
        )
        assert response.json().keys() == {'transaction_id', 'result_code'}
        assert_valid_transaction_id(response=response)
        assert_valid_date_header(response=response)
        result_code = response.json()['result_code']
        transaction_id = response.json()['transaction_id']
        assert result_code == ResultCodes.BAD_IMAGE.value
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id": '
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )
        assert response.text == expected_text


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestMaximumImageFileSize:
    """
    Tests for maximum image file sizes.
    """

    def test_png(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        According to
        https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query.
        the maximum file size is "2MiB for PNG".

        Above this limit, a ``ConnectionError`` is raised.
        We do not test exactly at this limit, but that may be beneficial in the
        future.
        """
        max_bytes = 2 * 1024 * 1024
        width = height = 835
        png_not_too_large = make_image_file(
            file_format='PNG',
            color_space='RGB',
            width=width,
            height=height,
        )

        image_content = png_not_too_large.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        image_content_size = len(image_content)
        # We check that the image we created is just slightly smaller than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``make_image_file``.
        assert image_content_size < max_bytes
        assert (image_content_size * 1.05) > max_bytes

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert response.json()['results'] == []

        width += 1
        height += 1
        png_too_large = make_image_file(
            file_format='PNG',
            color_space='RGB',
            width=width,
            height=height,
        )

        image_content = png_too_large.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        image_content_size = len(image_content)
        # We check that the image we created is just slightly larger than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``make_image_file``.
        assert image_content_size > max_bytes
        assert (image_content_size * 0.95) < max_bytes

        with pytest.raises(requests.exceptions.ConnectionError):
            query(
                vuforia_database=vuforia_database,
                body=body,
            )

    def test_jpeg(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        According to
        https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query.
        the maximum file size is "512 KiB for JPEG".
        However, this test shows that the maximum size for JPEG is 2 MiB.

        Above this limit, a ``ConnectionError`` is raised.
        We do not test exactly at this limit, but that may be beneficial in the
        future.
        """
        max_bytes = 2 * 1024 * 1024
        width = height = 1865
        jpeg_not_too_large = make_image_file(
            file_format='JPEG',
            color_space='RGB',
            width=width,
            height=height,
        )

        image_content = jpeg_not_too_large.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        image_content_size = len(image_content)
        # We check that the image we created is just slightly smaller than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``make_image_file``.
        assert image_content_size < max_bytes
        assert (image_content_size * 1.05) > max_bytes

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert response.json()['results'] == []

        width = height = 1866
        jpeg_too_large = make_image_file(
            file_format='JPEG',
            color_space='RGB',
            width=width,
            height=height,
        )

        image_content = jpeg_too_large.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        image_content_size = len(image_content)
        # We check that the image we created is just slightly larger than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``make_image_file``.
        assert image_content_size > max_bytes
        assert (image_content_size * 0.95) < max_bytes

        with pytest.raises(requests.exceptions.ConnectionError):
            query(
                vuforia_database=vuforia_database,
                body=body,
            )


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestMaximumImageDimensions:
    """
    Tests for maximum image dimensions.
    """

    def test_max_height(self, vuforia_database: VuforiaDatabase) -> None:
        """
        An error is returned when an image with a height greater than 30000 is
        given.
        """
        width = 1
        max_height = 30000
        png_not_too_tall = make_image_file(
            file_format='PNG',
            color_space='RGB',
            width=width,
            height=max_height,
        )

        image_content = png_not_too_tall.getvalue()

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert response.json()['results'] == []

        png_too_tall = make_image_file(
            file_format='PNG',
            color_space='RGB',
            width=width,
            height=max_height + 1,
        )

        image_content = png_too_tall.getvalue()

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content_type='application/json',
        )
        assert response.json().keys() == {'transaction_id', 'result_code'}
        assert_valid_transaction_id(response=response)
        assert_valid_date_header(response=response)
        result_code = response.json()['result_code']
        transaction_id = response.json()['transaction_id']
        assert result_code == ResultCodes.BAD_IMAGE.value
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id": '
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )
        assert response.text == expected_text

    def test_max_width(self, vuforia_database: VuforiaDatabase) -> None:
        """
        An error is returned when an image with a width greater than 30000 is
        given.
        """
        height = 1
        max_width = 30000
        png_not_too_wide = make_image_file(
            file_format='PNG',
            color_space='RGB',
            width=max_width,
            height=height,
        )

        image_content = png_not_too_wide.getvalue()

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert response.json()['results'] == []

        png_too_wide = make_image_file(
            file_format='PNG',
            color_space='RGB',
            width=max_width + 1,
            height=height,
        )

        image_content = png_too_wide.getvalue()

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content_type='application/json',
        )
        assert response.json().keys() == {'transaction_id', 'result_code'}
        assert_valid_transaction_id(response=response)
        assert_valid_date_header(response=response)
        result_code = response.json()['result_code']
        transaction_id = response.json()['transaction_id']
        assert result_code == ResultCodes.BAD_IMAGE.value
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id": '
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )
        assert response.text == expected_text


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestImageFormats:
    """
    Tests for various image formats.
    """

    @pytest.mark.parametrize('file_format', ['png', 'jpeg'])
    def test_supported(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        file_format: str,
    ) -> None:
        """
        PNG and JPEG formats are supported.
        """
        image_buffer = io.BytesIO()
        pil_image = Image.open(high_quality_image)
        pil_image.save(image_buffer, file_format)
        image_content = image_buffer.getvalue()

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert response.json()['results'] == []

    def test_unsupported(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        File formats which are not PNG or JPEG are not supported.
        """
        file_format = 'tiff'
        image_buffer = io.BytesIO()
        pil_image = Image.open(high_quality_image)
        pil_image.save(image_buffer, file_format)
        image_content = image_buffer.getvalue()

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content_type='application/json',
        )
        assert response.json().keys() == {'transaction_id', 'result_code'}
        assert_valid_transaction_id(response=response)
        assert_valid_date_header(response=response)
        result_code = response.json()['result_code']
        transaction_id = response.json()['transaction_id']
        assert result_code == ResultCodes.BAD_IMAGE.value
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id": '
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )
        assert response.text == expected_text


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestProcessing:
    """
    Tests for targets in the processing state.
    """

    @pytest.mark.parametrize(
        'active_flag',
        [True, False],
    )
    def test_processing(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        active_flag: bool,
        vws_client: VWS,
    ) -> None:
        """
        When a target with a matching image is in the processing state it is
        not matched.

        Sometimes an `INTERNAL_SERVER_ERROR` response is returned.
        """
        image_content = high_quality_image.getvalue()

        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=active_flag,
            application_metadata=None,
        )

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        response = query(vuforia_database=vuforia_database, body=body)

        # We assert that after making a query, the target is in the processing
        # state.
        #
        # There is a race condition here.
        #
        # This is really a check that the test is valid.
        #
        # If the target is no longer in the processing state here, it may be
        # that the test was valid, but the target went into the processed
        # state.
        #
        # If the target is no longer in the processing state here, that is a
        # flaky test that is the test's fault and this must be rethought.
        target_details = vws_client.get_target_record(target_id=target_id)
        assert target_details.status == TargetStatuses.PROCESSING

        # Sometimes we get a 500 error, sometimes we do not.
        if response.status_code == HTTPStatus.OK:  # pragma: no cover
            assert response.json()['results'] == []
            assert_query_success(response=response)
            return

        # We do not mark this with "pragma: no cover" because we choose to
        # implement the mock to have this behavior.
        # The response text for a 500 response is not consistent.
        # Therefore we only test for consistent features.
        assert 'Error 500 Server Error' in response.text
        assert 'HTTP ERROR 500' in response.text
        assert 'Problem accessing /v1/query' in response.text

        assert_vwq_failure(
            response=response,
            content_type='text/html; charset=ISO-8859-1',
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestUpdate:
    """
    Tests for updated targets.
    """

    def test_updated_target(
        self,
        high_quality_image: io.BytesIO,
        different_high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        After a target is updated, only the new image can be matched.
        The match result includes the updated name, timestamp and application
        metadata.
        """
        image_content = high_quality_image.getvalue()
        metadata = b'example_metadata'
        metadata_encoded = base64.b64encode(metadata).decode('ascii')
        name = 'example_name'
        target_id = vws_client.add_target(
            name=name,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=metadata_encoded,
        )

        calendar.timegm(time.gmtime())

        vws_client.wait_for_target_processed(target_id=target_id)

        new_image_content = different_high_quality_image.getvalue()

        new_name = name + '2'
        new_metadata = metadata + b'2'
        new_metadata_encoded = base64.b64encode(new_metadata).decode('ascii')

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        response = query(vuforia_database=vuforia_database, body=body)
        [result] = response.json()['results']
        target_data = result['target_data']
        target_timestamp = target_data['target_timestamp']
        original_target_timestamp = int(target_timestamp)

        vws_client.update_target(
            target_id=target_id,
            name=new_name,
            image=different_high_quality_image,
            application_metadata=new_metadata_encoded,
        )

        approximate_target_updated = calendar.timegm(time.gmtime())

        vws_client.wait_for_target_processed(target_id=target_id)

        body = {'image': ('image.jpeg', new_image_content, 'image/jpeg')}
        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        [result] = response.json()['results']
        assert result.keys() == {'target_id', 'target_data'}
        assert result['target_id'] == target_id
        target_data = result['target_data']
        assert target_data.keys() == {
            'application_metadata',
            'name',
            'target_timestamp',
        }
        assert target_data['application_metadata'] == new_metadata_encoded
        assert target_data['name'] == new_name
        target_timestamp = target_data['target_timestamp']
        assert isinstance(target_timestamp, int)
        # In the future we might want to test that
        # target_timestamp > original_target_timestamp
        # However, this requires us to set the mock processing time at > 1
        # second.
        assert target_timestamp >= original_target_timestamp
        time_difference = abs(approximate_target_updated - target_timestamp)
        assert time_difference < 5

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}
        response = query(vuforia_database=vuforia_database, body=body)
        assert_query_success(response=response)
        assert response.json()['results'] == []


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestDeleted:
    """
    Tests for matching deleted targets.
    """

    def test_deleted(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        Within approximately 7 seconds of deleting a target, querying for its
        image results in an ``INTERNAL_SERVER_ERROR``.
        """
        image_content = high_quality_image.getvalue()
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        while True:
            response = query(vuforia_database=vuforia_database, body=body)
            # Sometimes the first response(s) include the old target.
            try:
                assert_query_success(response=response)
            except AssertionError:
                # The response text for a 500 response is not consistent.
                # Therefore we only test for consistent features.
                assert 'Error 500 Server Error' in response.text
                assert 'HTTP ERROR 500' in response.text
                assert 'Problem accessing /v1/query' in response.text

                assert_vwq_failure(
                    response=response,
                    content_type='text/html; charset=ISO-8859-1',
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                )

                return

    def test_deleted_and_wait(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        After waiting approximately 7 seconds (we wait more to be safer), a
        deleted target is not found when its image is queried for.
        """
        image_content = high_quality_image.getvalue()
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        # In practice, we have seen a delay of up to 30 seconds between
        # deleting a target and getting a valid response which has a result
        # array without the deleted item.
        total_waited = 0

        # We wait up to 60 seconds to be safe to avoid indefinite waits and
        # using up our quota.
        max_wait_seconds = 60

        # We do not want to retry immediately else we risk using our request
        # quota.
        sleep_seconds = 2

        server_error_seen = False

        while True:
            response = query(vuforia_database=vuforia_database, body=body)

            try:
                assert_query_success(response=response)
            except AssertionError:
                server_error_seen = True
                # The response text for a 500 response is not consistent.
                # Therefore we only test for consistent features.
                assert 'Error 500 Server Error' in response.text
                assert 'HTTP ERROR 500' in response.text
                assert 'Problem accessing /v1/query' in response.text
                time.sleep(sleep_seconds)
                total_waited += sleep_seconds
            else:
                if response.json()['results']:
                    [result] = response.json()['results']
                    assert result['target_id'] == target_id
                    # We never see the target ID after having seen the server
                    # error.
                    assert not server_error_seen
                    time.sleep(sleep_seconds)
                    total_waited += sleep_seconds
                else:
                    assert response.json()['results'] == []
                    break

            assert total_waited < max_wait_seconds

        # The deletion never takes effect immediately.
        assert total_waited

    def test_deleted_inactive(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        No error is returned when querying for an image of recently deleted,
        inactive target.
        """
        image_content = high_quality_image.getvalue()
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=False,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        assert response.json()['results'] == []


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestTargetStatusFailed:
    """
    Tests for targets with the status "failed".
    """

    def test_status_failed(
        self,
        image_file_failed_state: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        Targets with the status "failed" are not found in query results.
        """
        image_content = image_file_failed_state.getvalue()
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id)

        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=vuforia_database, body=body)
        assert_query_success(response=response)
        assert response.json()['results'] == []


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestDateFormats:
    """
    Tests for various date formats.

    The date format for the VWS API as per
    https://library.vuforia.com/articles/Training/Using-the-VWS-API.html must
    be in the rfc1123-date format.

    However, for the query endpoint, the documentation does not mention the
    format. It says:

    > The data format must exactly match the Date that is sent in the ‘Date’
    > header.
    """

    @pytest.mark.parametrize(
        'datetime_format',
        [
            '%a, %b %d %H:%M:%S %Y',
            '%a %b %d %H:%M:%S %Y',
            '%a, %d %b %Y %H:%M:%S',
            '%a %d %b %Y %H:%M:%S',
        ],
    )
    @pytest.mark.parametrize('include_tz', [True, False])
    def test_date_formats(
        self,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        datetime_format: str,
        include_tz: bool,
    ) -> None:
        """
        Test various date formats which are known to be accepted.

        We expect that more formats than this will be accepted.
        These are the accepted ones we know of at the time of writing.
        """
        image_content = high_quality_image.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        if include_tz:
            datetime_format += ' GMT'

        gmt = ZoneInfo('GMT')
        now = datetime.datetime.now(tz=gmt)
        date = now.strftime(datetime_format)
        request_path = '/v1/query'
        content, content_type_header = encode_multipart_formdata(body)
        method = POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
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
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
        )

        assert_query_success(response=response)
        assert response.json()['results'] == []


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    def test_inactive_project(
        self,
        inactive_database: VuforiaDatabase,
        high_quality_image: io.BytesIO,
    ) -> None:
        """
        If the project is inactive, a FORBIDDEN response is returned.
        """
        image_content = high_quality_image.getvalue()
        body = {'image': ('image.jpeg', image_content, 'image/jpeg')}

        response = query(vuforia_database=inactive_database, body=body)

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.FORBIDDEN,
            content_type='application/json',
        )
        assert response.json().keys() == {'transaction_id', 'result_code'}
        assert_valid_transaction_id(response=response)
        assert_valid_date_header(response=response)
        result_code = response.json()['result_code']
        transaction_id = response.json()['transaction_id']
        assert result_code == ResultCodes.INACTIVE_PROJECT.value
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id": '
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )
        assert response.text == expected_text
