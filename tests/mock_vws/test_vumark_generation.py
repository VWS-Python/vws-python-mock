"""
Tests for generating VuMark instances.
"""

import json
from http import HTTPMethod
from urllib.parse import urljoin

import pytest
import requests
from mock_vws.database import VuforiaDatabase
from vws_auth_tools import authorization_header, rfc_1123_date


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestVuMarkInstanceGeneration:
    """
    Tests for generating VuMark instances.
    """

    # Content type: svg+xml, image/png, application/pdf
    def test_generate_vumark_instance(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        date = rfc_1123_date()
        target_id = "TODO"
        request_path = f"/targets/{target_id}/instances"
        content_type = "image/png"
        method = HTTPMethod.POST

        data = {
            # TODO: Fill this in
            "instance_id": "EXAMPLE",
        }
        content = bytes(json.dumps(data), encoding="utf-8")

        authorization_string = authorization_header(
            access_key=vuforia_database.server_access_key,
            secret_key=vuforia_database.server_secret_key,
            method=method,
            content=content,
            content_type=content_type,
            date=date,
            request_path=request_path,
        )

        headers = {
            "Authorization": authorization_string,
            "Date": date,
            "Content-Type": content_type,
        }

        response = requests.request(
            method=method,
            url=urljoin("https://vws.vuforia.com/", request_path),
            headers=headers,
            data=content,
            timeout=30,
        )

        response_json = json.loads(s=response.text)
        assert isinstance(response_json, dict)

    def test_target_does_not_exist(self) -> None:
        url = "https://vws.vuforia.com/targets/{target_id}/instances"

    def test_invalid_instance_id(self) -> None:
        # Negative, too large, float, illegal characters
        # too many hex characters
        # string too long
        pass

    def test_target_status_is_processing(self) -> None:
        pass

    def test_target_status_is_failed(self) -> None:
        pass

    def test_cloud_target(self) -> None:
        pass

    def test_invalid_accept_header(self) -> None:
        pass

    def test_instance_id_not_given(self) -> None:
        pass

    def test_extra_fields_given(self) -> None:
        pass


# TODO: Fill in tests
# TODO: Look at query / cloud target validators for tests
# TODO: Make a VuMark instance database
# TODO: Make a VuMark instance in the database
# TODO: Add VuMark database credentials to secrets
# TODO: Docker container for VuMark
# TODO: Add new secrets to GitHub Actions
# TODO: Then create a library for the VuMark database
# TODO: Then update tests to use the library
