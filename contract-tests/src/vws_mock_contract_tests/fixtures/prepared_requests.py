"""Fixtures which prepare requests."""

import json
from http import HTTPMethod, HTTPStatus
from uuid import uuid4

import pytest
from vws_auth_tools import authorization_header, rfc_1123_date

from vws_mock_contract_tests.fixtures.credentials import VuMarkCloudDatabase
from vws_mock_contract_tests.utils import Endpoint


@pytest.fixture
def vumark_generate_instance(
    *,
    vumark_vuforia_database: VuMarkCloudDatabase,
    base_vws_url: str,
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
        base_url=base_vws_url,
        path_url=request_path,
        method=method,
        headers=headers,
        data=content,
        access_key=access_key,
        secret_key=secret_key,
    )
