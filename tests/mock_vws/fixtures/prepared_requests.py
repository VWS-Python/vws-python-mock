"""Fixtures which prepare requests."""

import base64
import io
import json
from http import HTTPMethod, HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from urllib3.filepost import encode_multipart_formdata
from vws import VWS
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import CloudDatabase
from tests.mock_vws.fixtures.credentials import VuMarkCloudDatabase
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.retries import RETRY_ON_TOO_MANY_REQUESTS

VWS_HOST = "https://vws.vuforia.com"
VWQ_HOST = "https://cloudreco.vuforia.com"


@RETRY_ON_TOO_MANY_REQUESTS
def _wait_for_target_processed(*, vws_client: VWS, target_id: str) -> None:
    """Wait for a target to be processed.

    We retry here because pytest-retry does not retry on exceptions
    raised in fixtures.

    See
    https://github.com/str0zzapreti/pytest-retry/issues/33.
    """
    vws_client.wait_for_target_processed(target_id=target_id)


@pytest.fixture
def add_target(
    vuforia_database: CloudDatabase,
    image_file_failed_state: io.BytesIO,
) -> Endpoint:
    """Return details of the endpoint for adding a target."""
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii"
    )
    date = rfc_1123_date()
    data = {
        "name": "example_name",
        "width": 1,
        "image": image_data_encoded,
    }
    request_path = "/targets"
    content_type = "application/json"
    method = HTTPMethod.POST

    content = json.dumps(obj=data).encode(encoding="utf-8")

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
        "Content-Length": str(object=len(content)),
        "Content-Type": content_type,
    }

    return Endpoint(
        successful_headers_status_code=HTTPStatus.CREATED,
        successful_headers_result_code=ResultCodes.TARGET_CREATED,
        base_url=VWS_HOST,
        path_url=request_path,
        method=method,
        headers=headers,
        data=content,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture
def delete_target(
    vuforia_database: CloudDatabase,
    target_id: str,
    vws_client: VWS,
) -> Endpoint:
    """Return details of the endpoint for deleting a target."""
    _wait_for_target_processed(vws_client=vws_client, target_id=target_id)
    date = rfc_1123_date()
    request_path = f"/targets/{target_id}"
    method = HTTPMethod.DELETE
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
        "Content-Length": str(object=len(content)),
    }

    return Endpoint(
        base_url=VWS_HOST,
        path_url=request_path,
        method=method,
        headers=headers,
        data=content,
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture
def database_summary(vuforia_database: CloudDatabase) -> Endpoint:
    """
    Return details of the endpoint for getting details about the
    database.
    """
    date = rfc_1123_date()
    request_path = "/summary"
    method = HTTPMethod.GET

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
        "Content-Length": str(object=len(content)),
        "Date": date,
    }

    return Endpoint(
        base_url=VWS_HOST,
        path_url=request_path,
        method=method,
        headers=headers,
        data=content,
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture
def get_duplicates(
    vuforia_database: CloudDatabase,
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
    method = HTTPMethod.GET

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
        "Content-Length": str(object=len(content)),
        "Date": date,
    }

    return Endpoint(
        base_url=VWS_HOST,
        path_url=request_path,
        method=method,
        headers=headers,
        data=content,
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture
def get_target(
    vuforia_database: CloudDatabase,
    target_id: str,
    vws_client: VWS,
) -> Endpoint:
    """Return details of the endpoint for getting details of a target."""
    _wait_for_target_processed(vws_client=vws_client, target_id=target_id)
    date = rfc_1123_date()
    request_path = f"/targets/{target_id}"
    method = HTTPMethod.GET

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
        "Content-Length": str(object=len(content)),
        "Date": date,
    }

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        base_url=VWS_HOST,
        path_url=request_path,
        method=method,
        headers=headers,
        data=content,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture
def target_list(vuforia_database: CloudDatabase) -> Endpoint:
    """Return details of the endpoint for getting a list of targets."""
    date = rfc_1123_date()
    request_path = "/targets"
    method = HTTPMethod.GET

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
        "Content-Length": str(object=len(content)),
        "Date": date,
    }

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        base_url=VWS_HOST,
        path_url=request_path,
        method=method,
        headers=headers,
        data=content,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture
def target_summary(
    vuforia_database: CloudDatabase,
    target_id: str,
    vws_client: VWS,
) -> Endpoint:
    """
    Return details of the endpoint for getting a summary report of a
    target.
    """
    _wait_for_target_processed(vws_client=vws_client, target_id=target_id)
    date = rfc_1123_date()
    request_path = f"/summary/{target_id}"
    method = HTTPMethod.GET

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
        "Content-Length": str(object=len(content)),
        "Date": date,
    }

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        base_url=VWS_HOST,
        path_url=request_path,
        method=method,
        headers=headers,
        data=content,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture
def update_target(
    vuforia_database: CloudDatabase,
    target_id: str,
    vws_client: VWS,
) -> Endpoint:
    """Return details of the endpoint for updating a target."""
    _wait_for_target_processed(vws_client=vws_client, target_id=target_id)
    data: dict[str, Any] = {}
    request_path = f"/targets/{target_id}"
    content = json.dumps(obj=data).encode(encoding="utf-8")
    content_type = "application/json"

    date = rfc_1123_date()
    method = HTTPMethod.PUT

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
        "Content-Length": str(object=len(content)),
        "Content-Type": content_type,
        "Date": date,
    }

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        base_url=VWS_HOST,
        path_url=request_path,
        method=method,
        headers=headers,
        data=content,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture
def query(
    vuforia_database: CloudDatabase,
    high_quality_image: io.BytesIO,
) -> Endpoint:
    """
    Return details of the endpoint for making an image recognition
    query.
    """
    image_content = high_quality_image.getvalue()
    date = rfc_1123_date()
    request_path = "/v1/query"
    files = {"image": ("image.jpeg", image_content, "image/jpeg")}
    method = HTTPMethod.POST

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
        "Content-Length": str(object=len(content)),
        "Date": date,
        "Content-Type": content_type_header,
    }

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=ResultCodes.SUCCESS,
        base_url=VWQ_HOST,
        path_url=request_path,
        method=method,
        headers=headers,
        data=content,
        access_key=access_key,
        secret_key=secret_key,
    )


@pytest.fixture
def vumark_generate_instance(
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> Endpoint:
    """Return details of the endpoint for generating a VuMark instance."""
    request_path = f"/targets/{vumark_vuforia_database.target_id}/instances"
    content_type = "application/json"
    method = HTTPMethod.POST
    content = json.dumps(obj={"instance_id": uuid4().hex}).encode(
        encoding="utf-8"
    )
    date = rfc_1123_date()

    access_key = vumark_vuforia_database.server_access_key
    secret_key = vumark_vuforia_database.server_secret_key
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
        "Accept": "image/png",
        "Authorization": authorization_string,
        "Content-Length": str(object=len(content)),
        "Content-Type": content_type,
        "Date": date,
    }

    return Endpoint(
        successful_headers_status_code=HTTPStatus.OK,
        successful_headers_result_code=None,
        base_url=VWS_HOST,
        path_url=request_path,
        method=method,
        headers=headers,
        data=content,
        access_key=access_key,
        secret_key=secret_key,
    )
