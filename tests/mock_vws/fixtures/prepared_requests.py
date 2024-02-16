"""
Fixtures which prepare requests.
"""
from __future__ import annotations

import base64
import json
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import pytest
import requests
from mock_vws._constants import ResultCodes
from requests_mock import DELETE, GET, POST, PUT
from urllib3.filepost import encode_multipart_formdata
from vws_auth_tools import authorization_header, rfc_1123_date

from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.retries import RETRY_ON_TOO_MANY_REQUESTS

if TYPE_CHECKING:
    import io

    from mock_vws.database import VuforiaDatabase
    from vws import VWS

VWS_HOST = "https://vws.vuforia.com"
VWQ_HOST = "https://cloudreco.vuforia.com"


@RETRY_ON_TOO_MANY_REQUESTS
def _wait_for_target_processed(vws_client: VWS, target_id: str) -> None:
    """
    Wait for a target to be processed.

    We retry here because pytest-retry does not retry on exceptions raised in
    fixtures.

    See https://github.com/str0zzapreti/pytest-retry/issues/33.
    """
    vws_client.wait_for_target_processed(target_id=target_id)


@pytest.fixture()
def add_target(
    vuforia_database: VuforiaDatabase,
    image_file_failed_state: io.BytesIO,
) -> Endpoint:
    """
    Return details of the endpoint for adding a target.
    """
    image_data = image_file_failed_state.read()
    image_data_encoded = base64.b64encode(image_data).decode("ascii")
    date = rfc_1123_date()
    data: dict[str, Any] = {
        "name": "example_name",
        "width": 1,
        "image": image_data_encoded,
    }
    request_path = "/targets"
    content_type = "application/json"
    method = POST

    content = bytes(json.dumps(data), encoding="utf-8")

    access_key = vuforia_database.server_access_key
    secret_key = vuforia_database.server_secret_key
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

    request = requests.Request(
        method=method,
        url=urljoin(base=VWS_HOST, url=request_path),
        headers=headers,
        data=content,
    )

    prepared_request = request.prepare()

    return Endpoint(
        successful_headers_status_code=HTTPStatus.CREATED,
        successful_headers_result_code=ResultCodes.TARGET_CREATED,
        prepared_request=prepared_request,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture()
def delete_target(
    vuforia_database: VuforiaDatabase,
    target_id: str,
    vws_client: VWS,
) -> Endpoint:
    """
    Return details of the endpoint for deleting a target.
    """
    _wait_for_target_processed(vws_client=vws_client, target_id=target_id)
    date = rfc_1123_date()
    request_path = f"/targets/{target_id}"
    method = DELETE
    content = b""

    access_key = vuforia_database.server_access_key
    secret_key = vuforia_database.server_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        content_type="",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
    }

    request = requests.Request(
        method=method,
        url=urljoin(base=VWS_HOST, url=request_path),
        headers=headers,
        data=content,
    )

    prepared_request = request.prepare()
    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        prepared_request=prepared_request,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture()
def database_summary(vuforia_database: VuforiaDatabase) -> Endpoint:
    """
    Return details of the endpoint for getting details about the database.
    """
    date = rfc_1123_date()
    request_path = "/summary"
    method = GET

    content = b""

    access_key = vuforia_database.server_access_key
    secret_key = vuforia_database.server_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        content_type="",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
    }

    request = requests.Request(
        method=method,
        url=urljoin(base=VWS_HOST, url=request_path),
        headers=headers,
        data=content,
    )

    prepared_request = request.prepare()

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        prepared_request=prepared_request,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture()
def get_duplicates(
    vuforia_database: VuforiaDatabase,
    target_id: str,
    vws_client: VWS,
) -> Endpoint:
    """
    Return details of the endpoint for getting potential duplicates of a
    target.
    """
    _wait_for_target_processed(vws_client=vws_client, target_id=target_id)
    date = rfc_1123_date()
    request_path = f"/duplicates/{target_id}"
    method = GET

    content = b""

    access_key = vuforia_database.server_access_key
    secret_key = vuforia_database.server_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        content_type="",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
    }

    request = requests.Request(
        method=method,
        url=urljoin(base=VWS_HOST, url=request_path),
        headers=headers,
        data=content,
    )

    prepared_request = request.prepare()

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        prepared_request=prepared_request,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture()
def get_target(
    vuforia_database: VuforiaDatabase,
    target_id: str,
    vws_client: VWS,
) -> Endpoint:
    """
    Return details of the endpoint for getting details of a target.
    """
    _wait_for_target_processed(vws_client=vws_client, target_id=target_id)
    date = rfc_1123_date()
    request_path = f"/targets/{target_id}"
    method = GET

    content = b""

    access_key = vuforia_database.server_access_key
    secret_key = vuforia_database.server_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        content_type="",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
    }

    request = requests.Request(
        method=method,
        url=urljoin(base=VWS_HOST, url=request_path),
        headers=headers,
        data=content,
    )

    prepared_request = request.prepare()

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        prepared_request=prepared_request,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture()
def target_list(vuforia_database: VuforiaDatabase) -> Endpoint:
    """
    Return details of the endpoint for getting a list of targets.
    """
    date = rfc_1123_date()
    request_path = "/targets"
    method = GET

    content = b""

    access_key = vuforia_database.server_access_key
    secret_key = vuforia_database.server_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        content_type="",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
    }

    request = requests.Request(
        method=method,
        url=urljoin(base=VWS_HOST, url=request_path),
        headers=headers,
        data=content,
    )

    prepared_request = request.prepare()

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        prepared_request=prepared_request,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture()
def target_summary(
    vuforia_database: VuforiaDatabase,
    target_id: str,
    vws_client: VWS,
) -> Endpoint:
    """
    Return details of the endpoint for getting a summary report of a target.
    """
    _wait_for_target_processed(vws_client=vws_client, target_id=target_id)
    date = rfc_1123_date()
    request_path = f"/summary/{target_id}"
    method = GET

    content = b""

    access_key = vuforia_database.server_access_key
    secret_key = vuforia_database.server_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        content_type="",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
    }

    request = requests.Request(
        method=method,
        url=urljoin(base=VWS_HOST, url=request_path),
        headers=headers,
        data=content,
    )

    prepared_request = request.prepare()

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        prepared_request=prepared_request,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture()
def update_target(
    vuforia_database: VuforiaDatabase,
    target_id: str,
    vws_client: VWS,
) -> Endpoint:
    """
    Return details of the endpoint for updating a target.
    """
    _wait_for_target_processed(vws_client=vws_client, target_id=target_id)
    data: dict[str, Any] = {}
    request_path = f"/targets/{target_id}"
    content = bytes(json.dumps(data), encoding="utf-8")
    content_type = "application/json"

    date = rfc_1123_date()
    method = PUT

    access_key = vuforia_database.server_access_key
    secret_key = vuforia_database.server_secret_key
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

    request = requests.Request(
        method=method,
        url=urljoin(base=VWS_HOST, url=request_path),
        headers=headers,
        data=content,
    )

    prepared_request = request.prepare()

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        prepared_request=prepared_request,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture()
def query(
    vuforia_database: VuforiaDatabase,
    high_quality_image: io.BytesIO,
) -> Endpoint:
    """
    Return details of the endpoint for making an image recognition query.
    """
    image_content = high_quality_image.read()
    date = rfc_1123_date()
    request_path = "/v1/query"
    files = {"image": ("image.jpeg", image_content, "image/jpeg")}
    method = POST

    content, content_type_header = encode_multipart_formdata(fields=files)

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

    request = requests.Request(
        method=method,
        url=urljoin(base=VWQ_HOST, url=request_path),
        headers=headers,
        data=content,
    )

    prepared_request = request.prepare()

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        prepared_request=prepared_request,
        access_key=access_key,
        secret_key=secret_key,
    )
