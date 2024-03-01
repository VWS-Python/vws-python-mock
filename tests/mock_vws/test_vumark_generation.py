"""
Tests for generating VuMark instances.
"""

import json

import pytest
import requests
from mock_vws.database import VuforiaDatabase
from requests_mock import PUT
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
        url = f"https://vws.vuforia.com/targets/{target_id}/instances"
        # TODO: Fill this in
        response = requests.post(url=url)
        response_json = json.loads(s=response.text)

        data = {
            # TODO: Fill this in
            "instance_id": "EXAMPLE",
        }
        content = bytes(json.dumps(data), encoding="utf-8")

        assert isinstance(response_json, dict)
        authorization_string = authorization_header(
            access_key=vuforia_database.server_access_key,
            secret_key=vuforia_database.server_secret_key,
            method=PUT,
            content=content,
            content_type=content_type,
            date=date,
            request_path=request_path,
        )

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


# TODO: Fill in tests
# TODO: Look at query / cloud target validators for tests
# TODO: Make a VuMark instance database
# TODO: Make a VuMark instance in the database
# TODO: Add VuMark database credentials to secrets
# TODO: Add new secrets to GitHub Actions
# TODO: Then create a library for the VuMark database
# TODO: Then update tests to use the library
