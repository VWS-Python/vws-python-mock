"""Tests for the VuMark generation web API."""

import base64
import io
import json
from http import HTTPMethod, HTTPStatus
from uuid import uuid4

import pytest
import requests
from vws import VWS
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws.database import VuforiaDatabase
from tests.mock_vws.fixtures.credentials import VuMarkVuforiaDatabase
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend

_VWS_HOST = "https://vws.vuforia.com"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestGenerateInstance:
    """Tests for VuMark instance generation."""

    _TINY_PNG = base64.b64decode(
        s=(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
            "2mP8/x8AAwMCAO7Zl6kAAAAASUVORK5CYII="
        ),
    )

    @staticmethod
    def _create_mock_target_id(vuforia_database: VuforiaDatabase) -> str:
        """Create and return a target ID for mock backends."""
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        return vws_client.add_target(
            name=uuid4().hex,
            width=1,
            image=io.BytesIO(initial_bytes=TestGenerateInstance._TINY_PNG),
            active_flag=True,
            application_metadata=None,
        )

    def test_generate_instance_success(
        self,
        verify_mock_vuforia: VuforiaBackend,
        vuforia_database: VuforiaDatabase,
        vumark_vuforia_database: VuMarkVuforiaDatabase,
    ) -> None:
        """A VuMark instance can be generated with valid template settings."""
        if verify_mock_vuforia == VuforiaBackend.REAL:
            server_access_key = vumark_vuforia_database.server_access_key
            server_secret_key = vumark_vuforia_database.server_secret_key
            target_id = vumark_vuforia_database.target_id
        else:
            server_access_key = vuforia_database.server_access_key
            server_secret_key = vuforia_database.server_secret_key
            target_id = self._create_mock_target_id(
                vuforia_database=vuforia_database
            )

        request_path = f"/targets/{target_id}/instances"
        content_type = "application/json"
        generated_instance_id = uuid4().hex
        content = json.dumps(
            obj={"instance_id": generated_instance_id}
        ).encode(encoding="utf-8")
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
        assert (
            response.headers["Content-Type"].split(sep=";")[0] == "image/png"
        )
        assert response.content.startswith(_PNG_SIGNATURE)
        assert len(response.content) > len(_PNG_SIGNATURE)
