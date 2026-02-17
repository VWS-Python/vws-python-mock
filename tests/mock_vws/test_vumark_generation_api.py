"""Tests for the VuMark generation web API."""

import json
from http import HTTPMethod, HTTPStatus
from uuid import uuid4

import pytest
import requests
from vws_auth_tools import authorization_header, rfc_1123_date

from tests.mock_vws.fixtures.credentials import VuMarkVuforiaDatabase

_VWS_HOST = "https://vws.vuforia.com"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.mark.usefixtures("verify_mock_vuforia")
def test_generate_instance_success(
    vumark_vuforia_database: VuMarkVuforiaDatabase,
) -> None:
    """A VuMark instance can be generated with valid template settings."""
    if vumark_vuforia_database.target_id.startswith("<"):
        pytest.skip(
            reason=(
                "VuMark target ID is a placeholder. "
                "Set VUMARK_VUFORIA_TARGET_ID."
            ),
        )

    request_path = f"/targets/{vumark_vuforia_database.target_id}/instances"
    content_type = "application/json"
    generated_instance_id = uuid4().hex
    content = json.dumps(obj={"instance_id": generated_instance_id}).encode(
        encoding="utf-8"
    )
    date = rfc_1123_date()
    authorization_string = authorization_header(
        access_key=vumark_vuforia_database.server_access_key,
        secret_key=vumark_vuforia_database.server_secret_key,
        method=HTTPMethod.POST,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    response = requests.post(
        url=_VWS_HOST + request_path,
        headers={
            "Accept": "image/png",
            "Authorization": authorization_string,
            "Content-Length": str(object=len(content)),
            "Content-Type": content_type,
            "Date": date,
        },
        data=content,
        timeout=30,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.headers["Content-Type"].split(sep=";")[0] == "image/png"
    assert response.content.startswith(_PNG_SIGNATURE)
    assert len(response.content) > len(_PNG_SIGNATURE)
