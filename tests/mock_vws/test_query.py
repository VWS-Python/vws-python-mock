"""Tests for the mock of the query endpoint.

https://developer.vuforia.com/library/web-api/vuforia-query-web-api.
"""

import base64
import calendar
import copy
import datetime
import io
import json
import textwrap
import time
import uuid
from http import HTTPMethod, HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import pytest
import requests
from dirty_equals import IsInstance
from PIL import Image
from tenacity import Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from urllib3.filepost import encode_multipart_formdata
from vws import VWS, CloudRecoService
from vws.exceptions.cloud_reco_exceptions import (
    BadImageError,
    InactiveProjectError,
    MaxNumResultsOutOfRangeError,
)
from vws.exceptions.custom_exceptions import RequestEntityTooLargeError
from vws.reports import TargetStatuses
from vws.response import Response
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import make_image_file
from tests.mock_vws.utils.assertions import (
    assert_query_success,
    assert_valid_transaction_id,
    assert_vwq_failure,
)
from tests.mock_vws.utils.too_many_requests import handle_server_errors

if TYPE_CHECKING:
    from collections.abc import Iterable

VWQ_HOST = "https://cloudreco.vuforia.com"

_JETTY_CONTENT_TYPE_ERROR = textwrap.dedent(
    text="""\
    <html>
    <head>
    <meta http-equiv="Content-Type" content="text/html;charset=ISO-8859-1"/>
    <title>Error 400 Bad Request</title>
    </head>
    <body>
    <h2>HTTP ERROR 400 Bad Request</h2>
    <table>
    <tr><th>URI:</th><td>http://cloudreco.vuforia.com/v1/query</td></tr>
    <tr><th>STATUS:</th><td>400</td></tr>
    <tr><th>MESSAGE:</th><td>Bad Request</td></tr>
    </table>
    <hr/><a href="https://jetty.org/">Powered by Jetty:// 12.0.20</a><hr/>

    </body>
    </html>
    """,
)

_NGINX_REQUEST_ENTITY_TOO_LARGE_ERROR = textwrap.dedent(
    text="""\
    <html>\r
    <head><title>413 Request Entity Too Large</title></head>\r
    <body>\r
    <center><h1>413 Request Entity Too Large</h1></center>\r
    <hr><center>nginx</center>\r
    </body>\r
    </html>\r
    """,
)


def _query(
    *,
    vuforia_database: VuforiaDatabase,
    body: dict[str, Any],
) -> Response:
    """Make a request to the endpoint to make an image recognition query.

    Args:
        vuforia_database: The credentials to use to connect to
            Vuforia.
        body: The request body to send in ``multipart/formdata`` format.

    Returns:
        The response returned by the API.
    """
    date = rfc_1123_date()
    request_path = "/v1/query"
    content, content_type_header = encode_multipart_formdata(fields=body)
    method = HTTPMethod.POST

    access_key = vuforia_database.client_access_key
    secret_key = vuforia_database.client_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        # Note that this is not the actual Content-Type header value sent.
        content_type="multipart/form-data",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
        "Content-Type": content_type_header,
    }

    vwq_host = "https://cloudreco.vuforia.com"
    requests_response = requests.request(
        method=method,
        url=urljoin(base=vwq_host, url=request_path),
        headers=headers,
        data=content,
        timeout=30,
    )

    vws_response = Response(
        text=requests_response.text,
        url=requests_response.url,
        status_code=requests_response.status_code,
        headers=dict(requests_response.headers),
        request_body=requests_response.request.body,
        tell_position=requests_response.raw.tell(),
    )
    handle_server_errors(response=vws_response)
    return vws_response


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestContentType:
    """Tests for the Content-Type header."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames=(
            "content_type",
            "resp_status_code",
            "resp_content_type",
            "resp_cache_control",
            "resp_text",
        ),
        argvalues=[
            (
                "text/html",
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                None,
                None,
                "",
            ),
            (
                "",
                HTTPStatus.BAD_REQUEST,
                "text/html;charset=iso-8859-1",
                "must-revalidate,no-cache,no-store",
                _JETTY_CONTENT_TYPE_ERROR,
            ),
            (
                "*/*",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "application/json",
                None,
                "RESTEASY007550: Unable to get boundary for multipart",
            ),
            (
                "text/*",
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                None,
                None,
                "",
            ),
            (
                "text/plain",
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                None,
                None,
                "",
            ),
        ],
    )
    def test_incorrect_no_boundary(
        *,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        content_type: str,
        resp_status_code: int,
        resp_content_type: str | None,
        resp_cache_control: str | None,
        resp_text: str,
    ) -> None:
        """With bad Content-Type headers we get a variety of results."""
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = "/v1/query"
        body = {"image": ("image.jpeg", image_content, "image/jpeg")}
        content, _ = encode_multipart_formdata(fields=body)
        method = HTTPMethod.POST

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
            "Authorization": authorization_string,
            "Date": date,
            "Content-Type": content_type,
        }

        requests_response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
            timeout=30,
        )

        vws_response = Response(
            text=requests_response.text,
            url=requests_response.url,
            status_code=requests_response.status_code,
            headers=dict(requests_response.headers),
            request_body=requests_response.request.body,
            tell_position=requests_response.raw.tell(),
        )

        if resp_status_code != HTTPStatus.INTERNAL_SERVER_ERROR:
            handle_server_errors(response=vws_response)

        assert requests_response.text == resp_text
        assert_vwq_failure(
            response=vws_response,
            status_code=resp_status_code,
            content_type=resp_content_type,
            cache_control=resp_cache_control,
            www_authenticate=None,
            connection="keep-alive",
        )

    @staticmethod
    def test_incorrect_with_boundary(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If a Content-Type header which is not ``multipart/form-data`` is
        given
        with the correct boundary, an ``UNSUPPORTED_MEDIA_TYPE`` response
        is
        given.
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = "/v1/query"
        body = {"image": ("image.jpeg", image_content, "image/jpeg")}
        content, content_type_header = encode_multipart_formdata(fields=body)
        method = HTTPMethod.POST

        content_type = "text/html"

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

        _, boundary = content_type_header.split(sep=";")

        content_type = "text/html; " + boundary
        headers = {
            "Authorization": authorization_string,
            "Date": date,
            "Content-Type": content_type,
        }

        requests_response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
            timeout=30,
        )

        vws_response = Response(
            text=requests_response.text,
            url=requests_response.url,
            status_code=requests_response.status_code,
            headers=dict(requests_response.headers),
            request_body=requests_response.request.body,
            tell_position=requests_response.raw.tell(),
        )
        handle_server_errors(response=vws_response)
        assert not requests_response.text
        assert_vwq_failure(
            response=vws_response,
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            content_type=None,
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames="content_type",
        argvalues=[
            "multipart/form-data",
            "multipart/form-data; extra",
            "multipart/form-data; extra=1",
        ],
    )
    def test_no_boundary(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        content_type: str,
    ) -> None:
        """
        If no boundary is given, an ``INTERNAL_SERVER_ERROR`` is
        returned.
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = "/v1/query"
        body = {"image": ("image.jpeg", image_content, "image/jpeg")}
        content, _ = encode_multipart_formdata(fields=body)
        method = HTTPMethod.POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            # Note that this is not the actual Content-Type header value sent.
            content_type="multipart/form-data",
            date=date,
            request_path=request_path,
        )

        headers = {
            "Authorization": authorization_string,
            "Date": date,
            "Content-Type": content_type,
        }

        requests_response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
            timeout=30,
        )

        vws_response = Response(
            text=requests_response.text,
            url=requests_response.url,
            status_code=requests_response.status_code,
            headers=dict(requests_response.headers),
            request_body=requests_response.request.body,
            tell_position=requests_response.raw.tell(),
        )
        expected_text = "RESTEASY007550: Unable to get boundary for multipart"
        assert requests_response.text == expected_text
        assert_vwq_failure(
            response=vws_response,
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content_type="application/json",
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )

    @staticmethod
    def test_bogus_boundary(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """If a bogus boundary is given, a ``BAD_REQUEST`` is returned."""
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = "/v1/query"
        body = {"image": ("image.jpeg", image_content, "image/jpeg")}
        content, _ = encode_multipart_formdata(fields=body)
        method = HTTPMethod.POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            # Note that this is not the actual Content-Type header value sent.
            content_type="multipart/form-data",
            date=date,
            request_path=request_path,
        )

        headers = {
            "Authorization": authorization_string,
            "Date": date,
            "Content-Type": "multipart/form-data; boundary=example_boundary",
        }

        requests_response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
            timeout=30,
        )

        vws_response = Response(
            text=requests_response.text,
            url=requests_response.url,
            status_code=requests_response.status_code,
            headers=dict(requests_response.headers),
            request_body=requests_response.request.body,
            tell_position=requests_response.raw.tell(),
        )
        handle_server_errors(response=vws_response)

        expected_text = "No image."
        assert requests_response.text == expected_text
        assert_vwq_failure(
            response=vws_response,
            status_code=HTTPStatus.BAD_REQUEST,
            content_type="application/json",
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )

    @staticmethod
    def test_extra_section(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If sections that are not the boundary section are given in the
        header,
        that is fine.
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = "/v1/query"
        body = {"image": ("image.jpeg", image_content, "image/jpeg")}
        content, content_type_header = encode_multipart_formdata(fields=body)
        method = HTTPMethod.POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            # Note that this is not the actual Content-Type header value sent.
            content_type="multipart/form-data",
            date=date,
            request_path=request_path,
        )

        headers = {
            "Authorization": authorization_string,
            "Date": date,
            "Content-Type": content_type_header + "; extra=1",
        }

        requests_response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
            timeout=30,
        )

        vws_response = Response(
            text=requests_response.text,
            url=requests_response.url,
            status_code=requests_response.status_code,
            headers=dict(requests_response.headers),
            request_body=requests_response.request.body,
            tell_position=requests_response.raw.tell(),
        )
        handle_server_errors(response=vws_response)
        assert_query_success(response=vws_response)
        response_json = json.loads(s=requests_response.text)
        assert response_json["results"] == []


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestSuccess:
    """Tests for successful calls to the query endpoint."""

    @staticmethod
    def test_no_results(
        high_quality_image: io.BytesIO,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """
        When there are no matching images in the database, an empty list
        of
        results is returned.
        """
        results = cloud_reco_client.query(image=high_quality_image)
        assert results == []

    @staticmethod
    def test_match_exact(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """
        If the exact high quality image that was added is queried for,
        target
        data is shown.
        """
        image_file = high_quality_image
        image_content = image_file.getvalue()
        metadata_encoded = base64.b64encode(s=b"example").decode(
            encoding="ascii"
        )
        name = "example_name"

        target_id = vws_client.add_target(
            name=name,
            width=1,
            image=image_file,
            active_flag=True,
            application_metadata=metadata_encoded,
        )

        approximate_target_created = calendar.timegm(tuple=time.gmtime())

        vws_client.wait_for_target_processed(target_id=target_id)

        body = {"image": ("image.jpeg", image_content, "image/jpeg")}

        response = _query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        response_json = json.loads(s=response.text)
        (result,) = response_json["results"]
        assert result == {
            "target_id": target_id,
            "target_data": {
                "application_metadata": metadata_encoded,
                "name": name,
                "target_timestamp": IsInstance(expected_type=int),
            },
        }
        target_timestamp = int(result["target_data"]["target_timestamp"])
        time_difference = abs(approximate_target_created - target_timestamp)
        max_time_difference = 5
        assert time_difference < max_time_difference

    @staticmethod
    def test_low_quality_image(
        image_file_success_state_low_rating: io.BytesIO,
        cloud_reco_client: CloudRecoService,
        vws_client: VWS,
    ) -> None:
        """
        If the exact low quality image that was added is queried for, no
        results are returned.
        """
        image_file = image_file_success_state_low_rating
        metadata_encoded = base64.b64encode(s=b"example").decode(
            encoding="ascii"
        )
        name = "example_name"

        target_id = vws_client.add_target(
            name=name,
            width=1,
            image=image_file,
            active_flag=True,
            application_metadata=metadata_encoded,
        )

        vws_client.wait_for_target_processed(target_id=target_id)
        matching_targets = cloud_reco_client.query(image=image_file)
        assert not matching_targets

    @staticmethod
    def test_match_similar(
        high_quality_image: io.BytesIO,
        different_high_quality_image: io.BytesIO,
        vws_client: VWS,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """
        If a similar image to one that was added is queried for, target
        data is
        shown.
        """
        metadata_encoded = base64.b64encode(s=b"example").decode(
            encoding="ascii"
        )
        name_matching = "example_name_matching"
        name_not_matching = "example_name_not_matching"

        target_id_matching = vws_client.add_target(
            name=name_matching,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=metadata_encoded,
        )

        target_id_not_matching = vws_client.add_target(
            name=name_not_matching,
            width=1,
            image=different_high_quality_image,
            active_flag=True,
            application_metadata=metadata_encoded,
        )

        vws_client.wait_for_target_processed(target_id=target_id_matching)
        vws_client.wait_for_target_processed(target_id=target_id_not_matching)

        similar_image_buffer = io.BytesIO()
        similar_image_data = copy.copy(x=high_quality_image)
        pil_similar_image = Image.open(fp=similar_image_data)
        # Re-save means similar but not identical.
        pil_similar_image.save(fp=similar_image_buffer, format="JPEG")

        (matching_target,) = cloud_reco_client.query(
            image=similar_image_buffer,
            max_num_results=5,
        )

        assert matching_target.target_id == target_id_matching

    @staticmethod
    def test_not_base64_encoded_processable(
        high_quality_image: io.BytesIO,
        vws_client: VWS,
        not_base64_encoded_processable: str,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """
        Vuforia accepts some metadata strings which are not valid
        base64.
        When a target with such a string is matched by a query, Vuforia
        returns
        an interesting result:

        * If the metadata string is a length one greater than a multiple of 4,
          the last character is ignored.
        * If the metadata is two greater than a multiple of 4, the result is
          padded, then decoded, then encoded.
        * If the metadata is three greater than a multiple of 4, the result is
          padded, then decoded, then encoded.
        """
        target_id = vws_client.add_target(
            name="example_name",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=not_base64_encoded_processable,
        )

        vws_client.wait_for_target_processed(target_id=target_id)

        query_results = cloud_reco_client.query(image=high_quality_image)

        (result,) = query_results
        assert result.target_data is not None
        query_metadata = result.target_data.application_metadata
        mod_4_to_expected_metadata_original = {
            1: not_base64_encoded_processable[:-1],
            2: not_base64_encoded_processable + "==",
            3: not_base64_encoded_processable + "=",
        }
        expected_metadata_original = mod_4_to_expected_metadata_original[
            len(not_base64_encoded_processable) % 4
        ]
        expected_metadata = base64.b64encode(
            s=base64.b64decode(s=expected_metadata_original),
        )
        assert query_metadata == expected_metadata.decode()


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestIncorrectFields:
    """Tests for incorrect and unexpected fields."""

    @staticmethod
    def test_missing_image(vuforia_database: VuforiaDatabase) -> None:
        """
        If an image is not given, a ``BAD_REQUEST`` response is
        returned.
        """
        response = _query(vuforia_database=vuforia_database, body={})

        assert response.text == "No image."
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            content_type="application/json",
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )

    @staticmethod
    def test_extra_fields(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        If extra fields are given, a ``BAD_REQUEST`` response is
        returned.
        """
        image_content = high_quality_image.getvalue()
        body = {
            "image": ("image.jpeg", image_content, "image/jpeg"),
            "extra_field": (None, 1, "text/plain"),
        }

        response = _query(vuforia_database=vuforia_database, body=body)

        assert response.text == "Unknown parameters in the request."
        assert_vwq_failure(
            response=response,
            content_type="application/json",
            status_code=HTTPStatus.BAD_REQUEST,
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )

    @staticmethod
    def test_missing_image_and_extra_fields(
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """If extra fields are given and no image field is given, a
        ``BAD_REQUEST`` response is returned.

        The extra field error takes precedence.
        """
        body = {
            "extra_field": (None, 1, "text/plain"),
        }

        response = _query(vuforia_database=vuforia_database, body=body)

        assert response.text == "Unknown parameters in the request."
        assert_vwq_failure(
            response=response,
            content_type="application/json",
            status_code=HTTPStatus.BAD_REQUEST,
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestMaxNumResults:
    """Tests for the ``max_num_results`` parameter."""

    @staticmethod
    def test_default(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        vws_client: VWS,
    ) -> None:
        """The default ``max_num_results`` is 1."""
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
            "image": ("image.jpeg", image_content, "image/jpeg"),
        }

        response = _query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        response_json = json.loads(s=response.text)
        assert len(response_json["results"]) == 1

    @staticmethod
    @pytest.mark.parametrize(argnames="num_results", argvalues=[1, b"1", 50])
    def test_valid_accepted(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        num_results: int | bytes,
    ) -> None:
        """Numbers between 1 and 50 are valid inputs.

        We assert that the response is a success, but not that the
        maximum number of results is enforced.

        This is because uploading 50 images would be very slow.

        The documentation at
        https://developer.vuforia.com/library/web-api/vuforia-query-web-api
        states that this must be between 1 and 10, but in practice, 50 is the
        maximum.
        """
        image_content = high_quality_image.getvalue()
        body = {
            "image": ("image.jpeg", image_content, "image/jpeg"),
            "max_num_results": (None, num_results, "text/plain"),
        }

        response = _query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        response_json = json.loads(s=response.text)
        assert response_json["results"] == []

    @staticmethod
    def test_valid_works(
        high_quality_image: io.BytesIO,
        vws_client: VWS,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """A maximum of ``max_num_results`` results are returned."""
        _add_and_wait_for_targets(
            image=high_quality_image,
            vws_client=vws_client,
            num_targets=3,
        )

        max_num_results = 2

        result = cloud_reco_client.query(
            image=high_quality_image,
            max_num_results=max_num_results,
        )
        assert len(result) == max_num_results

    @staticmethod
    @pytest.mark.parametrize(argnames="num_results", argvalues=[-1, 0, 51])
    def test_out_of_range(
        high_quality_image: io.BytesIO,
        num_results: int,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """An error is returned if ``max_num_results`` is given as an
        integer
        out of the range (1, 50).

        The documentation at
        https://developer.vuforia.com/library/web-api/vuforia-query-web-api.
        states that this must be between 1 and 10, but in practice, 50 is the
        maximum.
        """
        with pytest.raises(
            expected_exception=MaxNumResultsOutOfRangeError,
        ) as exc_info:
            cloud_reco_client.query(
                image=high_quality_image,
                max_num_results=num_results,
            )

        expected_text = (
            f"Integer out of range ({num_results}) in form data part "
            "'max_result'. Accepted range is from 1 to 50 (inclusive)."
        )
        assert exc_info.value.response.text == expected_text
        assert_vwq_failure(
            response=exc_info.value.response,
            content_type="application/json",
            status_code=HTTPStatus.BAD_REQUEST,
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames="num_results",
        argvalues=[b"0.1", b"1.1", b"a", b"2147483648"],
    )
    def test_invalid_type(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        num_results: bytes,
    ) -> None:
        """An error is returned if ``max_num_results`` is given as
        something
        other than an integer.

        Integers greater than 2147483647 are not considered integers
        because they are bigger than Java's maximum integer.
        """
        image_content = high_quality_image.getvalue()
        body = {
            "image": ("image.jpeg", image_content, "image/jpeg"),
            "max_num_results": (None, num_results, "text/plain"),
        }
        response = _query(vuforia_database=vuforia_database, body=body)

        expected_text = (
            f"Invalid value '{num_results.decode()}' in form data part "
            "'max_result'. "
            "Expecting integer value in range from 1 to 50 (inclusive)."
        )
        assert response.text == expected_text
        assert_vwq_failure(
            response=response,
            content_type="application/json",
            status_code=HTTPStatus.BAD_REQUEST,
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )


def _add_and_wait_for_targets(
    *,
    image: io.BytesIO,
    vws_client: VWS,
    num_targets: int,
) -> None:
    """Add targets with the given image."""
    target_ids: Iterable[str] = set()
    for _ in range(num_targets):
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image,
            active_flag=True,
            application_metadata=None,
        )
        target_ids = {*target_ids, target_id}

    for created_target_id in target_ids:
        vws_client.wait_for_target_processed(target_id=created_target_id)


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestIncludeTargetData:
    """Tests for the ``include_target_data`` parameter."""

    @staticmethod
    def test_default(
        high_quality_image: io.BytesIO,
        vws_client: VWS,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """The default ``include_target_data`` is 'top'."""
        _add_and_wait_for_targets(
            image=high_quality_image,
            vws_client=vws_client,
            num_targets=2,
        )
        image_content = high_quality_image.getvalue()
        body = {
            "image": ("image.jpeg", image_content, "image/jpeg"),
            "max_num_results": (None, 2, "text/plain"),
        }

        response = _query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        response_json = json.loads(s=response.text)
        result_1, result_2 = response_json["results"]
        assert "target_data" in result_1
        assert "target_data" not in result_2

    @staticmethod
    @pytest.mark.parametrize(
        argnames="include_target_data",
        argvalues=["top", "TOP"],
    )
    def test_top(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        include_target_data: str,
        vws_client: VWS,
    ) -> None:
        """
        When ``include_target_data`` is set to "top" (case insensitive),
        only
        the first result includes target data.
        """
        _add_and_wait_for_targets(
            image=high_quality_image,
            vws_client=vws_client,
            num_targets=2,
        )
        image_content = high_quality_image.getvalue()
        body = {
            "image": ("image.jpeg", image_content, "image/jpeg"),
            "include_target_data": (None, include_target_data, "text/plain"),
            "max_num_results": (None, 2, "text/plain"),
        }

        response = _query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        response_json = json.loads(s=response.text)
        result_1, result_2 = response_json["results"]
        assert "target_data" in result_1
        assert "target_data" not in result_2

    @staticmethod
    @pytest.mark.parametrize(
        argnames="include_target_data",
        argvalues=["none", "NONE"],
    )
    def test_none(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        include_target_data: str,
        vws_client: VWS,
    ) -> None:
        """
        When ``include_target_data`` is set to "none" (case
        insensitive), no
        results include target data.
        """
        _add_and_wait_for_targets(
            image=high_quality_image,
            vws_client=vws_client,
            num_targets=2,
        )
        image_content = high_quality_image.getvalue()
        body = {
            "image": ("image.jpeg", image_content, "image/jpeg"),
            "include_target_data": (None, include_target_data, "text/plain"),
            "max_num_results": (None, 2, "text/plain"),
        }

        response = _query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        response_json = json.loads(s=response.text)
        result_1, result_2 = response_json["results"]
        assert "target_data" not in result_1
        assert "target_data" not in result_2

    @staticmethod
    @pytest.mark.parametrize(
        argnames="include_target_data",
        argvalues=["all", "ALL"],
    )
    def test_all(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        include_target_data: str,
        vws_client: VWS,
    ) -> None:
        """
        When ``include_target_data`` is set to "all" (case insensitive),
        all
        results include target data.
        """
        _add_and_wait_for_targets(
            image=high_quality_image,
            vws_client=vws_client,
            num_targets=2,
        )
        image_content = high_quality_image.getvalue()
        body = {
            "image": ("image.jpeg", image_content, "image/jpeg"),
            "include_target_data": (None, include_target_data, "text/plain"),
            "max_num_results": (None, 2, "text/plain"),
        }

        response = _query(vuforia_database=vuforia_database, body=body)

        assert_query_success(response=response)
        response_json = json.loads(s=response.text)
        result_1, result_2 = response_json["results"]
        assert "target_data" in result_1
        assert "target_data" in result_2

    @staticmethod
    @pytest.mark.parametrize(
        argnames="include_target_data",
        argvalues=["a", True, 0],
    )
    def test_invalid_value(
        *,
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        include_target_data: str | bool | int,
    ) -> None:
        """
        A ``BAD_REQUEST`` error is given when a string that is not one
        of
        'none', 'top' or 'all' (case insensitive).
        """
        image_content = high_quality_image.getvalue()
        body = {
            "image": ("image.jpeg", image_content, "image/jpeg"),
            "include_target_data": (None, include_target_data, "text/plain"),
        }
        response = _query(vuforia_database=vuforia_database, body=body)

        expected_text = (
            f"Invalid value '{str(object=include_target_data).lower()}' in "
            "form data part 'include_target_data'. "
            "Expecting one of the (unquoted) string values 'all', 'none' or "
            "'top'."
        )
        assert response.text == expected_text
        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.BAD_REQUEST,
            content_type="application/json",
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestAcceptHeader:
    """Tests for the ``Accept`` header."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames="extra_headers",
        argvalues=[
            {
                "Accept": "application/json",
            },
            {},
        ],
    )
    def test_valid(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        extra_headers: dict[str, str],
    ) -> None:
        """An ``Accept`` header can be given iff its value is
        "application/json".
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = "/v1/query"
        body = {"image": ("image.jpeg", image_content, "image/jpeg")}
        content, content_type_header = encode_multipart_formdata(fields=body)
        method = HTTPMethod.POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            # Note that this is not the actual Content-Type header value sent.
            content_type="multipart/form-data",
            date=date,
            request_path=request_path,
        )
        headers = {
            "Authorization": authorization_string,
            "Date": date,
            "Content-Type": content_type_header,
        } | extra_headers

        requests_response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
            timeout=30,
        )

        vws_response = Response(
            text=requests_response.text,
            url=requests_response.url,
            status_code=requests_response.status_code,
            headers=dict(requests_response.headers),
            request_body=requests_response.request.body,
            tell_position=requests_response.raw.tell(),
        )
        handle_server_errors(response=vws_response)
        assert_query_success(response=vws_response)
        response_json = json.loads(s=requests_response.text)
        assert response_json["results"] == []

    @staticmethod
    def test_invalid(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        A NOT_ACCEPTABLE response is returned if an ``Accept`` header is
        given
        with a value which is not "application/json".
        """
        image_content = high_quality_image.getvalue()
        date = rfc_1123_date()
        request_path = "/v1/query"
        body = {"image": ("image.jpeg", image_content, "image/jpeg")}
        content, content_type_header = encode_multipart_formdata(fields=body)
        method = HTTPMethod.POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            # Note that this is not the actual Content-Type header value sent.
            content_type="multipart/form-data",
            date=date,
            request_path=request_path,
        )

        headers = {
            "Authorization": authorization_string,
            "Date": date,
            "Content-Type": content_type_header,
            "Accept": "text/html",
        }

        requests_response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
            timeout=30,
        )

        vws_response = Response(
            text=requests_response.text,
            url=requests_response.url,
            status_code=requests_response.status_code,
            headers=dict(requests_response.headers),
            request_body=requests_response.request.body,
            tell_position=requests_response.raw.tell(),
        )
        handle_server_errors(response=vws_response)

        assert_vwq_failure(
            response=vws_response,
            status_code=HTTPStatus.NOT_ACCEPTABLE,
            content_type=None,
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestActiveFlag:
    """Tests for active versus inactive targets."""

    @staticmethod
    def test_inactive(
        high_quality_image: io.BytesIO,
        vws_client: VWS,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """Images which are not active are not matched."""
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=False,
            application_metadata=None,
        )

        vws_client.wait_for_target_processed(target_id=target_id)
        results = cloud_reco_client.query(image=high_quality_image)
        assert results == []


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestBadImage:
    """Tests for bad images."""

    @staticmethod
    def test_corrupted(
        corrupted_image_file: io.BytesIO,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """No error is returned when a corrupted image is given."""
        results = cloud_reco_client.query(image=corrupted_image_file)
        assert results == []

    @staticmethod
    def test_not_image(cloud_reco_client: CloudRecoService) -> None:
        """
        An ``UNPROCESSABLE_ENTITY`` response is returned when a non-
        image is
        given.
        """
        not_image_data = b"not_image_data"

        with pytest.raises(expected_exception=BadImageError) as exc_info:
            cloud_reco_client.query(
                image=io.BytesIO(initial_bytes=not_image_data)
            )

        response = exc_info.value.response

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content_type="application/json",
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )
        response_json = json.loads(s=response.text)
        assert isinstance(response_json, dict)
        assert response_json.keys() == {"transaction_id", "result_code"}
        assert_valid_transaction_id(response=response)
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id": '
            f'"{response_json["transaction_id"]}",'
            f'"result_code":"BadImage"'
            "}"
        )
        assert response.text == expected_text


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestMaximumImageFileSize:
    """Tests for maximum image file sizes."""

    @staticmethod
    def test_png(cloud_reco_client: CloudRecoService) -> None:
        """
        According to
        https://developer.vuforia.com/library/web-api/vuforia-query-web-
        api.
        the maximum file size is "2MiB for PNG".

        Above this limit, a ``REQUEST_ENTITY_TOO_LARGE`` response is returned.
        We do not test exactly at this limit, but that may be beneficial in the
        future.
        """
        max_bytes = 2 * 1024 * 1024
        width = height = 835
        png_not_too_large = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=width,
            height=height,
        )

        image_content = png_not_too_large.getvalue()

        image_content_size = len(image_content)
        # We check that the image we created is just slightly smaller than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``make_image_file``.
        assert image_content_size < max_bytes
        assert (image_content_size * 1.05) > max_bytes

        results = cloud_reco_client.query(image=png_not_too_large)
        assert results == []

        width += 1
        height += 1
        png_too_large = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=width,
            height=height,
        )

        image_content = png_too_large.getvalue()
        image_content_size = len(image_content)
        # We check that the image we created is just slightly larger than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``make_image_file``.
        assert image_content_size > max_bytes
        assert (image_content_size * 0.95) < max_bytes

        with pytest.raises(
            expected_exception=RequestEntityTooLargeError
        ) as exc_info:
            cloud_reco_client.query(image=png_too_large)

        response = exc_info.value.response

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            content_type="text/html",
            cache_control=None,
            www_authenticate=None,
            connection="Close",
        )
        assert response.text == _NGINX_REQUEST_ENTITY_TOO_LARGE_ERROR

    @staticmethod
    def test_jpeg(cloud_reco_client: CloudRecoService) -> None:
        """
        According to
        https://developer.vuforia.com/library/web-api/vuforia-query-web-
        api.
        the maximum file size is "512 KiB for JPEG".
        However, this test shows that the maximum size for JPEG is 2 MiB.

        Above this limit, a ``REQUEST_ENTITY_TOO_LARGE`` response is returned.
        We do not test exactly at this limit, but that may be beneficial in the
        future.
        """
        max_bytes = 2 * 1024 * 1024
        width = height = 1865
        jpeg_not_too_large = make_image_file(
            file_format="JPEG",
            color_space="RGB",
            width=width,
            height=height,
        )

        image_content = jpeg_not_too_large.getvalue()

        image_content_size = len(image_content)
        # We check that the image we created is just slightly smaller than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``make_image_file``.
        assert image_content_size < max_bytes
        assert (image_content_size * 1.05) > max_bytes

        results = cloud_reco_client.query(image=jpeg_not_too_large)
        assert results == []

        width = height = 1866
        jpeg_too_large = make_image_file(
            file_format="JPEG",
            color_space="RGB",
            width=width,
            height=height,
        )

        image_content = jpeg_too_large.getvalue()
        image_content_size = len(image_content)
        # We check that the image we created is just slightly larger than the
        # maximum file size.
        #
        # This is just because of the implementation details of
        # ``make_image_file``.
        assert image_content_size > max_bytes
        assert (image_content_size * 0.95) < max_bytes

        with pytest.raises(
            expected_exception=RequestEntityTooLargeError
        ) as exc_info:
            cloud_reco_client.query(image=jpeg_too_large)

        response = exc_info.value.response

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            content_type="text/html",
            cache_control=None,
            www_authenticate=None,
            connection="Close",
        )

        assert response.text == _NGINX_REQUEST_ENTITY_TOO_LARGE_ERROR


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestMaximumImageDimensions:
    """Tests for maximum image dimensions."""

    @staticmethod
    def test_max_height(
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """
        An error is returned when an image with a height greater than
        30000 is
        given.
        """
        width = 1
        max_height = 30000
        png_not_too_tall = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=width,
            height=max_height,
        )

        results = cloud_reco_client.query(image=png_not_too_tall)
        assert results == []

        png_too_tall = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=width,
            height=max_height + 1,
        )

        with pytest.raises(expected_exception=BadImageError) as exc_info:
            cloud_reco_client.query(image=png_too_tall)

        response = exc_info.value.response

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content_type="application/json",
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )

        response_json = json.loads(s=response.text)
        assert isinstance(response_json, dict)
        assert response_json.keys() == {"transaction_id", "result_code"}
        assert_valid_transaction_id(response=response)
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id": '
            f'"{response_json["transaction_id"]}",'
            f'"result_code":"BadImage"'
            "}"
        )
        assert response.text == expected_text

    @staticmethod
    def test_max_width(cloud_reco_client: CloudRecoService) -> None:
        """
        An error is returned when an image with a width greater than
        30000 is
        given.
        """
        height = 1
        max_width = 30000
        png_not_too_wide = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=max_width,
            height=height,
        )

        result = cloud_reco_client.query(image=png_not_too_wide)
        assert result == []

        png_too_wide = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=max_width + 1,
            height=height,
        )

        with pytest.raises(expected_exception=BadImageError) as exc_info:
            result = cloud_reco_client.query(image=png_too_wide)

        response = exc_info.value.response

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content_type="application/json",
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )

        response_json = json.loads(s=response.text)
        assert isinstance(response_json, dict)
        assert response_json.keys() == {"transaction_id", "result_code"}
        assert_valid_transaction_id(response=response)
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id": '
            f'"{response_json["transaction_id"]}",'
            f'"result_code":"BadImage"'
            "}"
        )
        assert response.text == expected_text

    @staticmethod
    def test_max_pixels(cloud_reco_client: CloudRecoService) -> None:
        """No error is returned for an 835 x 835 image."""
        # If we make this 836 then we hit REQUEST_ENTITY_TOO_LARGE errors.
        max_height = max_width = 835
        png_not_too_wide = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=max_width,
            height=max_height,
        )

        result = cloud_reco_client.query(image=png_not_too_wide)
        assert result == []


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestImageFormats:
    """Tests for various image formats."""

    @staticmethod
    @pytest.mark.parametrize(argnames="file_format", argvalues=["png", "jpeg"])
    def test_supported(
        high_quality_image: io.BytesIO,
        file_format: str,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """PNG and JPEG formats are supported."""
        image_buffer = io.BytesIO()
        pil_image = Image.open(fp=high_quality_image)
        pil_image.save(fp=image_buffer, format=file_format)
        image_content = image_buffer.getvalue()
        results = cloud_reco_client.query(
            image=io.BytesIO(initial_bytes=image_content)
        )
        assert results == []

    @staticmethod
    def test_unsupported(
        high_quality_image: io.BytesIO,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """File formats which are not PNG or JPEG are not supported."""
        file_format = "tiff"
        image_buffer = io.BytesIO()
        pil_image = Image.open(fp=high_quality_image)
        pil_image.save(fp=image_buffer, format=file_format)
        image_content = image_buffer.getvalue()

        with pytest.raises(expected_exception=BadImageError) as exc_info:
            cloud_reco_client.query(
                image=io.BytesIO(initial_bytes=image_content)
            )

        response = exc_info.value.response

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content_type="application/json",
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )
        response_json = json.loads(s=response.text)
        assert isinstance(response_json, dict)
        assert response_json.keys() == {"transaction_id", "result_code"}
        assert_valid_transaction_id(response=response)
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id": '
            f'"{response_json["transaction_id"]}",'
            f'"result_code":"BadImage"'
            "}"
        )
        assert response.text == expected_text


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestProcessing:
    """Tests for targets in the processing state."""

    @staticmethod
    @pytest.mark.parametrize(argnames="active_flag", argvalues=[True, False])
    def test_processing(
        high_quality_image: io.BytesIO,
        vws_client: VWS,
        cloud_reco_client: CloudRecoService,
        *,
        active_flag: bool,
    ) -> None:
        """
        When a target with a matching image is in the processing state
        it is
        not matched.
        """
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=active_flag,
            application_metadata=None,
        )
        matching_targets = cloud_reco_client.query(image=high_quality_image)
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

        assert matching_targets == []


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestUpdate:
    """Tests for updated targets."""

    @staticmethod
    def test_updated_target(
        high_quality_image: io.BytesIO,
        different_high_quality_image: io.BytesIO,
        vws_client: VWS,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """After a target is updated, only the new image can be matched.

        The match result includes the updated name, timestamp and
        application metadata.
        """
        metadata = b"example_metadata"
        metadata_encoded = base64.b64encode(s=metadata).decode(
            encoding="ascii"
        )
        name = "example_name"
        target_id = vws_client.add_target(
            name=name,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=metadata_encoded,
        )

        calendar.timegm(tuple=time.gmtime())

        vws_client.wait_for_target_processed(target_id=target_id)

        new_name = name + "2"
        new_metadata = metadata + b"2"
        new_metadata_encoded = base64.b64encode(s=new_metadata).decode(
            encoding="ascii"
        )

        results = cloud_reco_client.query(image=high_quality_image)
        (result,) = results
        assert result.target_data is not None
        original_target_timestamp = result.target_data.target_timestamp

        vws_client.update_target(
            target_id=target_id,
            name=new_name,
            image=different_high_quality_image,
            application_metadata=new_metadata_encoded,
        )

        approximate_target_updated = calendar.timegm(tuple=time.gmtime())

        vws_client.wait_for_target_processed(target_id=target_id)

        results = cloud_reco_client.query(image=different_high_quality_image)

        (result,) = results
        assert result.target_data is not None
        assert result.target_data.application_metadata == new_metadata_encoded
        assert result.target_data.name == new_name
        target_timestamp = result.target_data.target_timestamp
        # In the future we might want to test that
        # target_timestamp > original_target_timestamp
        # However, this requires us to set the mock processing time at > 1
        # second.
        assert target_timestamp >= original_target_timestamp
        time_difference = abs(
            approximate_target_updated - target_timestamp.timestamp(),
        )
        max_time_difference = 5
        assert time_difference < max_time_difference

        results = cloud_reco_client.query(image=high_quality_image)
        assert results == []


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestDeleted:
    """Tests for matching deleted targets."""

    @staticmethod
    def test_deleted_active(
        high_quality_image: io.BytesIO,
        vws_client: VWS,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """Deleted targets are not matched."""
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)

        # There is a race condition here.
        # In the real Vuforia, it takes some time for the target deletion
        # to be reflected in the query endpoint.
        #
        # This difference is documented in ``differences-to-vws.rst``.
        #
        # We retry to allow for this difference.
        for attempt in Retrying(
            wait=wait_fixed(wait=0.1),
            stop=stop_after_delay(max_delay=3),
            retry=retry_if_exception_type(
                exception_types=(AssertionError,),
            ),
            reraise=True,
        ):
            with attempt:
                results = cloud_reco_client.query(image=high_quality_image)
                assert results == []

    @staticmethod
    def test_deleted_inactive(
        high_quality_image: io.BytesIO,
        vws_client: VWS,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """
        No error is returned when querying for an image of recently
        deleted,
        inactive target.
        """
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            active_flag=False,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)
        results = cloud_reco_client.query(image=high_quality_image)
        assert results == []


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestTargetStatusFailed:
    """Tests for targets with the status "failed"."""

    @staticmethod
    def test_status_failed(
        image_file_failed_state: io.BytesIO,
        vws_client: VWS,
        cloud_reco_client: CloudRecoService,
    ) -> None:
        """Targets with the status "failed" are not found in query results."""
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image_file_failed_state,
            active_flag=True,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id)

        results = cloud_reco_client.query(image=image_file_failed_state)
        assert results == []


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestDateFormats:
    """Tests for various date formats.

    The date format for the VWS API as per
    https://library.vuforia.com/articles/Training/Using-the-VWS-API.html must
    be in the rfc1123-date format.

    However, for the query endpoint, the documentation does not mention the
    format. It says:

    > The data format must exactly match the Date that is sent in the `Date`
    > header.
    """

    @staticmethod
    @pytest.mark.parametrize(
        argnames="datetime_format",
        argvalues=[
            "%a, %b %d %H:%M:%S %Y",
            "%a %b %d %H:%M:%S %Y",
            "%a, %d %b %Y %H:%M:%S",
            "%a %d %b %Y %H:%M:%S",
        ],
    )
    @pytest.mark.parametrize(argnames="include_tz", argvalues=[True, False])
    def test_date_formats(
        high_quality_image: io.BytesIO,
        vuforia_database: VuforiaDatabase,
        datetime_format: str,
        *,
        include_tz: bool,
    ) -> None:
        """Test various date formats which are known to be accepted.

        We expect that more formats than this will be accepted. These
        are the accepted ones we know of at the time of writing.
        """
        image_content = high_quality_image.getvalue()
        body = {"image": ("image.jpeg", image_content, "image/jpeg")}

        if include_tz:
            datetime_format += " GMT"

        gmt = ZoneInfo(key="GMT")
        now = datetime.datetime.now(tz=gmt)
        date = now.strftime(format=datetime_format)
        request_path = "/v1/query"
        content, content_type_header = encode_multipart_formdata(fields=body)
        method = HTTPMethod.POST

        access_key = vuforia_database.client_access_key
        secret_key = vuforia_database.client_secret_key
        authorization_string = authorization_header(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            content=content,
            content_type="multipart/form-data",
            date=date,
            request_path=request_path,
        )

        headers = {
            "Authorization": authorization_string,
            "Date": date,
            "Content-Type": content_type_header,
        }

        requests_response = requests.request(
            method=method,
            url=urljoin(base=VWQ_HOST, url=request_path),
            headers=headers,
            data=content,
            timeout=30,
        )

        vws_response = Response(
            text=requests_response.text,
            url=requests_response.url,
            status_code=requests_response.status_code,
            headers=dict(requests_response.headers),
            request_body=requests_response.request.body,
            tell_position=requests_response.raw.tell(),
        )
        handle_server_errors(response=vws_response)
        assert_query_success(response=vws_response)
        response_json = json.loads(s=requests_response.text)
        assert response_json["results"] == []


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """Tests for inactive projects."""

    @staticmethod
    def test_inactive_project(
        high_quality_image: io.BytesIO,
        inactive_cloud_reco_client: CloudRecoService,
    ) -> None:
        """
        If the project is inactive, a FORBIDDEN response is
        returned.
        """
        with pytest.raises(
            expected_exception=InactiveProjectError
        ) as exc_info:
            inactive_cloud_reco_client.query(image=high_quality_image)

        response = exc_info.value.response

        assert_vwq_failure(
            response=response,
            status_code=HTTPStatus.FORBIDDEN,
            content_type="application/json",
            cache_control=None,
            www_authenticate=None,
            connection="keep-alive",
        )

        response_json = json.loads(s=response.text)
        assert isinstance(response_json, dict)

        assert response_json.keys() == {"transaction_id", "result_code"}
        assert_valid_transaction_id(response=response)
        # The separators are inconsistent and we test this.
        expected_text = (
            '{"transaction_id": '
            f'"{response_json["transaction_id"]}",'
            f'"result_code":"InactiveProject"'
            "}"
        )
        assert response.text == expected_text
