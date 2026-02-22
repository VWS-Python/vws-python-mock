"""Tests for the VuMark generation web API."""

import json
from http import HTTPMethod, HTTPStatus
from uuid import uuid4

import requests
from beartype import beartype
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws import MockVWS
from mock_vws._constants import ResultCodes
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.states import States
from mock_vws.target import VuMarkTarget

_VWS_HOST = "https://vws.vuforia.com"


@beartype
def _make_vumark_request(
    *,
    server_access_key: str,
    server_secret_key: str,
    target_id: str,
    instance_id: str,
    accept: str,
) -> requests.Response:
    """Send a VuMark instance generation request and return the
    response.
    """
    request_path = f"/targets/{target_id}/instances"
    content_type = "application/json"
    content = json.dumps(obj={"instance_id": instance_id}).encode(
        encoding="utf-8"
    )
    date = rfc_1123_date()
    authorization_string = authorization_header(
        access_key=server_access_key,
        secret_key=server_secret_key,
        method=HTTPMethod.POST,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    return requests.post(
        url=_VWS_HOST + request_path,
        headers={
            "Accept": accept,
            "Authorization": authorization_string,
            "Content-Length": str(object=len(content)),
            "Content-Type": content_type,
            "Date": date,
        },
        data=content,
        timeout=30,
    )


class TestInactiveDatabase:
    """Tests for VuMark generation with an inactive database."""

    @staticmethod
    def test_inactive_database() -> None:
        """Calling the VuMark generation API with credentials for an
        inactive database returns ProjectInactive.
        """
        vumark_target = VuMarkTarget(
            name="test-target",
            processing_time_seconds=0,
        )
        vumark_database = VuMarkDatabase(vumark_targets={vumark_target})
        inactive_cloud_database = CloudDatabase(
            state=States.PROJECT_INACTIVE,
        )

        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=inactive_cloud_database)
            mock.add_vumark_database(vumark_database=vumark_database)
            response = _make_vumark_request(
                server_access_key=inactive_cloud_database.server_access_key,
                server_secret_key=inactive_cloud_database.server_secret_key,
                target_id=vumark_target.target_id,
                instance_id=uuid4().hex,
                accept="image/png",
            )

        assert response.status_code == HTTPStatus.FORBIDDEN
        response_json = response.json()
        assert (
            response_json["result_code"] == ResultCodes.PROJECT_INACTIVE.value
        )
