"""Tests for Model Target Web API authentication.

Bearer token concerns which apply to every Model Target endpoint are
covered by the authorization header tests, via the
``model_target_endpoint`` fixture.
"""

from http import HTTPStatus

import pytest
import requests

from tests.mock_vws.fixtures.model_target_prepared_requests import (
    credentials_for_backend,
)
from tests.mock_vws.fixtures.vuforia_backends import (
    VuforiaBackend,
)
from tests.mock_vws.model_target_web_api.assertions import (
    assert_oauth2_error,
)
from tests.mock_vws.model_target_web_api.responses import parse_response_json
from tests.mock_vws.utils.assertions import (
    assert_model_target_status,
)
from tests.mock_vws.utils.model_target_retries import model_target_get


@pytest.mark.parametrize(
    argnames=("auth", "data", "status_code", "body"),
    argvalues=[
        pytest.param(
            None,
            {"grant_type": "client_credentials"},
            HTTPStatus.UNAUTHORIZED,
            {
                "error": "invalid_request",
                "error_description": (
                    "Missing or invalid authorization header"
                ),
            },
            id="missing-basic-auth",
        ),
        pytest.param(
            ("invalid-client-id", "invalid-client-secret"),
            {"grant_type": "client_credentials"},
            HTTPStatus.UNAUTHORIZED,
            {"error": "invalid_client"},
            id="invalid-client",
        ),
        pytest.param(
            ("invalid-client-id", "invalid-client-secret"),
            {"grant_type": "unsupported"},
            HTTPStatus.BAD_REQUEST,
            {"error": "unsupported_grant_type"},
            id="unsupported-grant-type",
        ),
        pytest.param(
            None,
            {"grant_type": "password", "password": "password"},
            HTTPStatus.BAD_REQUEST,
            {
                "error": "invalid_request",
                "error_description": "Missing username and/or password",
            },
            id="password-grant-missing-username",
        ),
        pytest.param(
            None,
            {
                "grant_type": "password",
                "username": "user@example.com",
            },
            HTTPStatus.BAD_REQUEST,
            {
                "error": "invalid_request",
                "error_description": "Missing username and/or password",
            },
            id="password-grant-missing-password",
        ),
    ],
)
def test_invalid_oauth2_token_request(
    *,
    base_vws_url: str,
    auth: tuple[str, str] | None,
    data: dict[str, str],
    status_code: HTTPStatus,
    body: dict[str, str],
) -> None:
    """Invalid OAuth2 token requests are rejected."""
    response = requests.post(
        url=f"{base_vws_url}/oauth2/token",
        auth=auth,
        data=data,
        timeout=30,
    )

    assert_oauth2_error(
        response=response,
        status_code=status_code,
        body=body,
    )


def test_password_grant(
    *,
    base_vws_url: str,
    verify_model_target_mock_vuforia: VuforiaBackend,
) -> None:
    """A username and password can be exchanged for a scoped token."""
    credentials = credentials_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    response = requests.post(
        url=f"{base_vws_url}/oauth2/token",
        data={
            "grant_type": "password",
            "username": credentials.username,
            "password": credentials.password,
            "scope": "modeltargets.standardmodeltarget.all",
        },
        timeout=30,
    )

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.OK,
    )
    assert isinstance(response.json()["access_token"], str)
    assert response.json()["token_type"] == "bearer"


def test_scoped_client_credentials_grant(
    *,
    base_vws_url: str,
    verify_model_target_mock_vuforia: VuforiaBackend,
) -> None:
    """A client credentials request accepts an explicit scope."""
    credentials = credentials_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    response = requests.post(
        url=f"{base_vws_url}/oauth2/token",
        auth=(credentials.client_id, credentials.client_secret),
        data={
            "grant_type": "client_credentials",
            "scope": "modeltargets.standardmodeltarget.all",
        },
        timeout=30,
    )

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.OK,
    )
    assert isinstance(response.json()["access_token"], str)
    assert response.json()["token_type"] == "bearer"


def test_insufficient_scope(
    *,
    base_vws_url: str,
    verify_model_target_mock_vuforia: VuforiaBackend,
) -> None:
    """A route rejects a token carrying only another route's scope."""
    credentials = credentials_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    token_response = requests.post(
        url=f"{base_vws_url}/oauth2/token",
        auth=(credentials.client_id, credentials.client_secret),
        data={
            "grant_type": "client_credentials",
            "scope": "modeltargets.standardmodeltarget.all",
        },
        timeout=30,
    )
    assert_model_target_status(
        response=token_response,
        status_codes=HTTPStatus.OK,
    )

    response = requests.post(
        url=f"{base_vws_url}/modeltargets/advancedDatasets",
        headers={
            "Authorization": (
                f"Bearer {token_response.json()['access_token']}"
            ),
        },
        json={},
        timeout=30,
    )

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.FORBIDDEN,
    )
    assert response.text == (
        "User does not have the required scopes to perform this action"
    )


def test_client_credentials_management(
    *,
    base_vws_url: str,
    verify_model_target_mock_vuforia: VuforiaBackend,
) -> None:
    """Client credentials can be created, listed, updated and
    deleted.
    """
    credentials = credentials_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    password_token_response = requests.post(
        url=f"{base_vws_url}/oauth2/token",
        data={
            "grant_type": "password",
            "username": credentials.username,
            "password": credentials.password,
            "scope": "oauth2.clientcredentials.all",
        },
        timeout=30,
    )
    assert_model_target_status(
        response=password_token_response,
        status_codes=HTTPStatus.OK,
    )
    headers = {
        "Authorization": (
            f"Bearer {password_token_response.json()['access_token']}"
        ),
    }
    create_response = requests.post(
        url=f"{base_vws_url}/oauth2/clientcredentials",
        headers=headers,
        json={
            "scopes": ["modeltargets.standardmodeltarget.all"],
        },
        timeout=30,
    )
    assert_model_target_status(
        response=create_response,
        status_codes=HTTPStatus.CREATED,
    )
    response_json = create_response.json()
    client_id: object = response_json["client_id"]
    client_secret: object = response_json["client_secret"]
    assert isinstance(client_id, str)
    assert isinstance(client_secret, str)

    try:
        list_response = model_target_get(
            url=f"{base_vws_url}/oauth2/clientcredentials",
            headers=headers,
            timeout=30,
        )
        assert_model_target_status(
            response=list_response,
            status_codes=HTTPStatus.OK,
        )
        created_entries = [
            entry
            for entry in list_response.json()
            if entry["clientId"] == client_id
        ]
        assert len(created_entries) == 1
        assert created_entries[0]["scopes"] == [
            "modeltargets.standardmodeltarget.all",
        ]

        update_response = requests.put(
            url=(
                f"{base_vws_url}/oauth2/clientcredentials/{client_id}/scopes"
            ),
            headers=headers,
            json=["modeltargets.advancedmodeltarget.all"],
            timeout=30,
        )
        assert_model_target_status(
            response=update_response,
            status_codes=HTTPStatus.OK,
        )
        assert update_response.json() == {
            "clientId": client_id,
            "scopes": ["modeltargets.advancedmodeltarget.all"],
        }

        client_token_response = requests.post(
            url=f"{base_vws_url}/oauth2/token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        assert_model_target_status(
            response=client_token_response,
            status_codes=HTTPStatus.OK,
        )
        client_access_token = parse_response_json(
            response=client_token_response,
        )["access_token"]
        assert isinstance(client_access_token, str)
        insufficient_response = requests.post(
            url=f"{base_vws_url}/modeltargets/datasets",
            headers={
                "Authorization": f"Bearer {client_access_token}",
            },
            json={},
            timeout=30,
        )
        assert_model_target_status(
            response=insufficient_response,
            status_codes=HTTPStatus.FORBIDDEN,
        )
    finally:
        delete_response = requests.delete(
            url=(f"{base_vws_url}/oauth2/clientcredentials/{client_id}"),
            headers=headers,
            timeout=30,
        )
        assert_model_target_status(
            response=delete_response,
            status_codes=HTTPStatus.NO_CONTENT,
        )

    missing_client_id = "000000000000000000000"
    missing_response = requests.delete(
        url=(f"{base_vws_url}/oauth2/clientcredentials/{missing_client_id}"),
        headers=headers,
        timeout=30,
    )
    assert_model_target_status(
        response=missing_response,
        status_codes=HTTPStatus.NOT_FOUND,
    )
    assert missing_response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": (
                f"Clientcredential with ID={missing_client_id} not found"
            ),
            "target": "clientcredential",
        },
    }
