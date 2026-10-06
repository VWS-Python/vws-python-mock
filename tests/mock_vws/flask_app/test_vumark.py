"""Tests for VuMark through the Flask app."""

import json
import uuid
from http import HTTPMethod, HTTPStatus

import requests
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import VuMarkDatabase
from mock_vws.target import VuMarkTarget
from tests.mock_vws.flask_app.helpers import EXAMPLE_URL_FOR_TARGET_MANAGER


def test_processing_target_returns_forbidden() -> None:
    """A VuMark target still processing returns 403 when generating
    an instance via the Flask app.
    """
    vumark_target = VuMarkTarget(
        name="processing-target",
        processing_time_seconds=9999,
    )
    vumark_database = VuMarkDatabase(
        vumark_targets=set(),
    )

    vumark_databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/vumark_databases"
    response = requests.post(
        url=vumark_databases_url,
        json=vumark_database.to_dict(),
        timeout=30,
    )
    assert response.status_code == HTTPStatus.CREATED
    database_data = json.loads(s=response.text)

    vumark_targets_url = (
        f"{vumark_databases_url}"
        f"/{database_data['database_name']}/vumark_targets"
    )
    response = requests.post(
        url=vumark_targets_url,
        json=vumark_target.to_dict(),
        timeout=30,
    )
    assert response.status_code == HTTPStatus.CREATED

    request_path = f"/targets/{vumark_target.target_id}/instances"
    content_type = "application/json"
    content = json.dumps(
        obj={"instance_id": uuid.uuid4().hex},
    ).encode(encoding="utf-8")
    date = rfc_1123_date()
    authorization_string = authorization_header(
        access_key=vumark_database.server_access_key,
        secret_key=vumark_database.server_secret_key,
        method=HTTPMethod.POST,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    response = requests.post(
        url="https://vws.vuforia.com" + request_path,
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

    assert response.status_code == HTTPStatus.FORBIDDEN
    response_json = response.json()
    assert (
        response_json["result_code"]
        == ResultCodes.TARGET_STATUS_NOT_SUCCESS.value
    )
