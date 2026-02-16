"""Tests for the VuMark generation web API."""

import json
import uuid
from http import HTTPMethod, HTTPStatus

import requests
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws.database import VuforiaDatabase

_VWS_HOST = "https://vws.vuforia.com"


def test_generate_instance_for_missing_target(
    vumark_vuforia_database: VuforiaDatabase,
) -> None:
    """The VuMark generation API can be called with signed credentials."""
    request_path = f"/targets/{uuid.uuid4().hex}/instances"
    content_type = "application/json"
    content = json.dumps(obj={"instance_id": "1"}).encode(encoding="utf-8")
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

    assert response.status_code == HTTPStatus.NOT_FOUND
    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert response_json["result_code"] in {"NoSuchTarget", "UnknownTarget"}
