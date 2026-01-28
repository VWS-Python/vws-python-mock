"""Tests for the VuMark Generation API endpoint."""

import io
import json
import uuid
from http import HTTPMethod, HTTPStatus

import pytest
import requests
from vws import VWS
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws import MockVWS
from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase

VWS_HOST = "https://vws.vuforia.com"


def _generate_vumark_instance(
    *,
    database: VuforiaDatabase,
    target_id: str,
    instance_id: str | int | None,
    accept: str,
) -> requests.Response:
    """Generate a VuMark instance.

    Args:
        database: The Vuforia database credentials.
        target_id: The target ID.
        instance_id: The VuMark instance ID.
        accept: The Accept header value.

    Returns:
        The response from the API.
    """
    request_path = f"/targets/{target_id}/instances"
    content = json.dumps(obj={"instance_id": instance_id}).encode("utf-8")
    date = rfc_1123_date()
    content_type = "application/json"

    authorization_string = authorization_header(
        access_key=database.server_access_key,
        secret_key=database.server_secret_key,
        method=HTTPMethod.POST,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
        "Content-Length": str(len(content)),
        "Content-Type": content_type,
        "Accept": accept,
    }

    url = VWS_HOST + request_path
    return requests.post(url=url, data=content, headers=headers, timeout=30)


def _generate_vumark_instance_with_body(
    *,
    database: VuforiaDatabase,
    target_id: str,
    body: dict[str, str | int | None],
    accept: str,
) -> requests.Response:
    """Generate a VuMark instance with a custom body.

    Args:
        database: The Vuforia database credentials.
        target_id: The target ID.
        body: The request body.
        accept: The Accept header value.

    Returns:
        The response from the API.
    """
    request_path = f"/targets/{target_id}/instances"
    content = json.dumps(obj=body).encode("utf-8")
    date = rfc_1123_date()
    content_type = "application/json"

    authorization_string = authorization_header(
        access_key=database.server_access_key,
        secret_key=database.server_secret_key,
        method=HTTPMethod.POST,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
        "Content-Length": str(len(content)),
        "Content-Type": content_type,
        "Accept": accept,
    }

    url = VWS_HOST + request_path
    return requests.post(url=url, data=content, headers=headers, timeout=30)


class TestSuccessfulGeneration:
    """Tests for successful VuMark instance generation."""

    @staticmethod
    def test_svg_generation(image_file_failed_state: io.BytesIO) -> None:
        """SVG images can be generated."""
        database = VuforiaDatabase()
        with MockVWS() as mock:
            mock.add_database(database=database)
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )

            target_id = vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=image_file_failed_state,
                active_flag=True,
                application_metadata=None,
            )

            response = _generate_vumark_instance(
                database=database,
                target_id=target_id,
                instance_id="test123",
                accept="image/svg+xml",
            )

            assert response.status_code == HTTPStatus.OK
            assert response.headers["Content-Type"] == "image/svg+xml"
            # Verify the response contains valid SVG
            assert b"<?xml" in response.content
            assert b"<svg" in response.content
            assert b"test123" in response.content

    @staticmethod
    def test_png_generation(image_file_failed_state: io.BytesIO) -> None:
        """PNG images can be generated."""
        database = VuforiaDatabase()
        with MockVWS() as mock:
            mock.add_database(database=database)
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )

            target_id = vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=image_file_failed_state,
                active_flag=True,
                application_metadata=None,
            )

            response = _generate_vumark_instance(
                database=database,
                target_id=target_id,
                instance_id="test456",
                accept="image/png",
            )

            assert response.status_code == HTTPStatus.OK
            assert response.headers["Content-Type"] == "image/png"
            # Verify the response contains PNG magic bytes
            assert response.content[:8] == b"\x89PNG\r\n\x1a\n"

    @staticmethod
    def test_pdf_generation(image_file_failed_state: io.BytesIO) -> None:
        """PDF documents can be generated."""
        database = VuforiaDatabase()
        with MockVWS() as mock:
            mock.add_database(database=database)
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )

            target_id = vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=image_file_failed_state,
                active_flag=True,
                application_metadata=None,
            )

            response = _generate_vumark_instance(
                database=database,
                target_id=target_id,
                instance_id="test789",
                accept="application/pdf",
            )

            assert response.status_code == HTTPStatus.OK
            assert response.headers["Content-Type"] == "application/pdf"
            # Verify the response contains PDF header
            assert response.content.startswith(b"%PDF-")


class TestInvalidAcceptHeader:
    """Tests for invalid Accept headers."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames="accept_header",
        argvalues=[
            "text/html",
            "application/json",
            "image/jpeg",
            "",
            "invalid",
        ],
        ids=[
            "text/html",
            "application/json",
            "image/jpeg (not supported)",
            "empty",
            "invalid",
        ],
    )
    def test_invalid_accept_header(
        image_file_failed_state: io.BytesIO,
        accept_header: str,
    ) -> None:
        """An error is returned for invalid Accept headers."""
        database = VuforiaDatabase()
        with MockVWS() as mock:
            mock.add_database(database=database)
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )

            target_id = vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=image_file_failed_state,
                active_flag=True,
                application_metadata=None,
            )

            response = _generate_vumark_instance(
                database=database,
                target_id=target_id,
                instance_id="test123",
                accept=accept_header,
            )

            assert response.status_code == HTTPStatus.BAD_REQUEST
            response_json = response.json()
            assert (
                response_json["result_code"]
                == ResultCodes.INVALID_ACCEPT_HEADER.value
            )


class TestInvalidInstanceId:
    """Tests for invalid instance IDs."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames="instance_id",
        argvalues=[
            "",
            None,
        ],
        ids=[
            "empty string",
            "None",
        ],
    )
    def test_invalid_instance_id(
        image_file_failed_state: io.BytesIO,
        instance_id: str | None,
    ) -> None:
        """An error is returned for invalid instance IDs."""
        database = VuforiaDatabase()
        with MockVWS() as mock:
            mock.add_database(database=database)
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )

            target_id = vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=image_file_failed_state,
                active_flag=True,
                application_metadata=None,
            )

            response = _generate_vumark_instance(
                database=database,
                target_id=target_id,
                instance_id=instance_id,
                accept="image/svg+xml",
            )

            assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
            response_json = response.json()
            assert (
                response_json["result_code"]
                == ResultCodes.INVALID_INSTANCE_ID.value
            )

    @staticmethod
    def test_missing_instance_id(
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """An error is returned when instance_id is missing from the body.

        The key validator rejects the request with a "Fail" error (400)
        because instance_id is a required field.
        """
        database = VuforiaDatabase()
        with MockVWS() as mock:
            mock.add_database(database=database)
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )

            target_id = vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=image_file_failed_state,
                active_flag=True,
                application_metadata=None,
            )

            response = _generate_vumark_instance_with_body(
                database=database,
                target_id=target_id,
                body={},  # No instance_id
                accept="image/svg+xml",
            )

            # Missing required keys return a "Fail" error
            assert response.status_code == HTTPStatus.BAD_REQUEST
            response_json = response.json()
            assert response_json["result_code"] == ResultCodes.FAIL.value

    @staticmethod
    def test_integer_instance_id(
        image_file_failed_state: io.BytesIO,
    ) -> None:
        """An error is returned when instance_id is not a string."""
        database = VuforiaDatabase()
        with MockVWS() as mock:
            mock.add_database(database=database)
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )

            target_id = vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=image_file_failed_state,
                active_flag=True,
                application_metadata=None,
            )

            response = _generate_vumark_instance(
                database=database,
                target_id=target_id,
                instance_id=12345,
                accept="image/svg+xml",
            )

            assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
            response_json = response.json()
            assert (
                response_json["result_code"]
                == ResultCodes.INVALID_INSTANCE_ID.value
            )


class TestResponseHeaders:
    """Tests for response headers."""

    @staticmethod
    def test_response_headers(image_file_failed_state: io.BytesIO) -> None:
        """The response includes expected headers."""
        database = VuforiaDatabase()
        with MockVWS() as mock:
            mock.add_database(database=database)
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            )

            target_id = vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=image_file_failed_state,
                active_flag=True,
                application_metadata=None,
            )

            response = _generate_vumark_instance(
                database=database,
                target_id=target_id,
                instance_id="test123",
                accept="image/svg+xml",
            )

            assert response.status_code == HTTPStatus.OK
            assert response.headers["Connection"] == "keep-alive"
            assert response.headers["server"] == "envoy"
            assert response.headers["Content-Type"] == "image/svg+xml"
            assert "Content-Length" in response.headers
            assert "Date" in response.headers
