"""Tests for VuMark through the Flask app."""

import json
import uuid
from http import HTTPMethod, HTTPStatus

import pytest
import requests
from freezegun import freeze_time
from vws import VuMarkService
from vws.vumark_accept import VuMarkAccept
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import VuMarkDatabase
from mock_vws.target import VuMarkTarget


@pytest.mark.parametrize(
    argnames="server_time",
    argvalues=["2026-10-08 12:00:00", "2026-10-08 12:00:00.500000"],
    ids=["behind", "equal"],
)
def test_zero_processing_target_generates_instance(
    *, target_manager_url: str, server_time: str
) -> None:
    """Serialized zero-duration targets generate without a clock wait."""
    with freeze_time(time_to_freeze="2026-10-08 12:00:00.500000"):
        target = VuMarkTarget(name="example")
        database = VuMarkDatabase()
        database_dict = database.to_dict()
        target_dict = target.to_dict()

    with freeze_time(time_to_freeze=server_time):
        response = requests.post(
            url=target_manager_url + "/vumark_databases",
            json=database_dict,
            timeout=30,
        )
        assert response.status_code == HTTPStatus.CREATED
        response = requests.post(
            url=(
                f"{target_manager_url}/vumark_databases"
                f"/{database.database_name}/vumark_targets"
            ),
            json=target_dict,
            timeout=30,
        )
        assert response.status_code == HTTPStatus.CREATED
        client = VuMarkService(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        image = client.generate_vumark_instance(
            target_id=target.target_id,
            instance_id="example-instance",
            accept=VuMarkAccept.PNG,
        )

    assert image.startswith(b"\x89PNG\r\n\x1a\n")


def test_processing_target_returns_forbidden(target_manager_url: str) -> None:
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

    vumark_databases_url = target_manager_url + "/vumark_databases"
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
