"""Tests for the VuMark generation web API."""

import json
from http import HTTPMethod, HTTPStatus
from uuid import uuid4

import pytest
import requests
from vws import VWS
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import CloudDatabase
from tests.mock_vws.fixtures.credentials import VuMarkCloudDatabase
from tests.mock_vws.utils import make_image_file

_VWS_HOST = "https://vws.vuforia.com"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PDF_SIGNATURE = b"%PDF"
_SVG_START = b"<"


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


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestGenerateInstance:
    """Tests for the VuMark instance generation endpoint."""

    @pytest.mark.parametrize(
        argnames=("accept", "expected_content_type", "expected_signature"),
        argvalues=[
            pytest.param("image/png", "image/png", _PNG_SIGNATURE, id="png"),
            pytest.param(
                "image/svg+xml",
                "image/svg+xml",
                _SVG_START,
                id="svg",
            ),
            pytest.param(
                "application/pdf",
                "application/pdf",
                _PDF_SIGNATURE,
                id="pdf",
            ),
        ],
    )
    @staticmethod
    def test_generate_instance_format(
        accept: str,
        expected_content_type: str,
        expected_signature: bytes,
        vumark_vuforia_database: VuMarkCloudDatabase,
    ) -> None:
        """A VuMark instance can be generated in the requested format."""
        response = _make_vumark_request(
            server_access_key=vumark_vuforia_database.server_access_key,
            server_secret_key=vumark_vuforia_database.server_secret_key,
            target_id=vumark_vuforia_database.target_id,
            instance_id=uuid4().hex,
            accept=accept,
        )

        assert response.status_code == HTTPStatus.OK
        assert (
            response.headers["Content-Type"].split(sep=";")[0]
            == expected_content_type
        )
        assert response.content.strip().startswith(expected_signature)
        assert len(response.content) > len(expected_signature)

    @staticmethod
    def test_invalid_accept_header(
        vumark_vuforia_database: VuMarkCloudDatabase,
    ) -> None:
        """An unsupported Accept header returns an error."""
        response = _make_vumark_request(
            server_access_key=vumark_vuforia_database.server_access_key,
            server_secret_key=vumark_vuforia_database.server_secret_key,
            target_id=vumark_vuforia_database.target_id,
            instance_id=uuid4().hex,
            accept="text/plain",
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        response_json = response.json()
        assert (
            response_json["result_code"]
            == ResultCodes.INVALID_ACCEPT_HEADER.value
        )

    @staticmethod
    def test_empty_instance_id(
        vumark_vuforia_database: VuMarkCloudDatabase,
    ) -> None:
        """An empty instance_id returns InvalidInstanceId."""
        response = _make_vumark_request(
            server_access_key=vumark_vuforia_database.server_access_key,
            server_secret_key=vumark_vuforia_database.server_secret_key,
            target_id=vumark_vuforia_database.target_id,
            instance_id="",
            accept="image/png",
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        response_json = response.json()
        assert (
            response_json["result_code"]
            == ResultCodes.INVALID_INSTANCE_ID.value
        )

    @staticmethod
    def test_non_vumark_database(
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """Generating a VuMark instance for a target in a non-VuMark
        database returns InvalidTargetType.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        image = make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=8,
            height=8,
        )
        target_id = vws_client.add_target(
            name="test",
            width=1,
            image=image,
            active_flag=True,
            application_metadata=None,
        )
        response = _make_vumark_request(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
            target_id=target_id,
            instance_id=uuid4().hex,
            accept="image/png",
        )
        assert response.status_code == HTTPStatus.FORBIDDEN
        response_json = response.json()
        assert (
            response_json["result_code"] == ResultCodes.INVALID_TARGET_TYPE.value
        )
