"""Tests for making requests with incorrect keys."""

from http import HTTPStatus

import pytest
from vws import VuMarkService
from vws.exceptions.vws_exceptions import AuthenticationFailureError, FailError
from vws.vumark_accept import VuMarkAccept

from vws_mock_contract_tests.fixtures.credentials import VuMarkCloudDatabase


def test_bad_access_key_services(
    vumark_vuforia_database: VuMarkCloudDatabase, base_vws_url: str
) -> None:
    """
    If the server access key given does not match any database, a
    ``Fail``
    response is returned.
    """
    vws_client = VuMarkService(
        server_access_key="example",
        server_secret_key=vumark_vuforia_database.server_secret_key,
        base_vws_url=base_vws_url,
    )
    with pytest.raises(expected_exception=FailError) as exc:
        _ = vws_client.generate_vumark_instance(
            target_id=vumark_vuforia_database.target_id,
            instance_id="123",
            accept=VuMarkAccept.PNG,
        )
    assert exc.value.response.status_code == HTTPStatus.BAD_REQUEST


def test_bad_secret_key_services(
    vumark_vuforia_database: VuMarkCloudDatabase, base_vws_url: str
) -> None:
    """
    If the server secret key given is incorrect, an
    ``AuthenticationFailureError`` response is returned.
    """
    vws_client = VuMarkService(
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key="example",
        base_vws_url=base_vws_url,
    )
    with pytest.raises(expected_exception=AuthenticationFailureError):
        _ = vws_client.generate_vumark_instance(
            target_id=vumark_vuforia_database.target_id,
            instance_id="123",
            accept=VuMarkAccept.PNG,
        )
