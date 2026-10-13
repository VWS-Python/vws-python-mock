"""Cover mock-only OAuth2 and validation error paths."""

import base64
from http import HTTPStatus

import pytest
import requests

from mock_vws import MockVWS
from tests.mock_vws.model_target_web_api.authentication import (
    MOCK_BEARER_TOKEN,
)
from tests.mock_vws.model_target_web_api.responses import parse_response_json
from tests.mock_vws.model_target_web_api.sample_data import (
    MODEL,
    STATE_CONFIGURATION,
    UNAUTHENTICATED_DATASET_REQUEST,
)
from tests.mock_vws.utils.assertions import (
    assert_model_target_status,
)


def _management_token(*, base_vws_url: str) -> str:
    """Return a token which can manage client credentials."""
    response = requests.post(
        url=f"{base_vws_url}/oauth2/token",
        data={
            "grant_type": "password",
            "username": "user@example.com",
            "password": "password",
            "scope": "oauth2.clientcredentials.all",
        },
        timeout=30,
    )
    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.OK,
    )
    access_token: object = response.json()["access_token"]
    assert isinstance(access_token, str)
    return access_token


def test_oauth2_grant_errors(*, base_vws_url: str) -> None:
    """Invalid passwords and scopes are rejected."""
    with MockVWS(base_vws_url=base_vws_url):
        invalid_password = requests.post(
            url=f"{base_vws_url}/oauth2/token",
            data={
                "grant_type": "password",
                "username": "user@example.com",
                "password": "wrong",
            },
            timeout=30,
        )
        assert_model_target_status(
            response=invalid_password,
            status_codes=HTTPStatus.UNAUTHORIZED,
        )
        assert invalid_password.json()["error"] == "invalid_grant"

        invalid_scope = requests.post(
            url=f"{base_vws_url}/oauth2/token",
            auth=("client-id", "client-secret"),
            data={"scope": "not.a.scope"},
            timeout=30,
        )
        assert_model_target_status(
            response=invalid_scope,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
        assert invalid_scope.json()["error"] == "invalid_scope"


def test_client_credential_authentication_errors(*, base_vws_url: str) -> None:
    """Credential-management routes enforce bearer-token validity and
    scope.
    """
    headers: list[dict[str, str]] = [
        {},
        {"Authorization": "Bearer malformed"},
        {"Authorization": "Bearer e30.e30.signature"},
        {"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
    ]
    with MockVWS(base_vws_url=base_vws_url):
        for request_headers in headers:
            response = requests.get(
                url=f"{base_vws_url}/oauth2/clientcredentials",
                headers=request_headers,
                timeout=30,
            )
            assert_model_target_status(
                response=response,
                status_codes={
                    HTTPStatus.UNAUTHORIZED,
                    HTTPStatus.FORBIDDEN,
                },
            )

        delete_response = requests.delete(
            url=f"{base_vws_url}/oauth2/clientcredentials/client-id",
            timeout=30,
        )
        assert_model_target_status(
            response=delete_response,
            status_codes=HTTPStatus.UNAUTHORIZED,
        )

        create_response = requests.post(
            url=f"{base_vws_url}/oauth2/clientcredentials",
            json={"scopes": []},
            timeout=30,
        )
        assert_model_target_status(
            response=create_response,
            status_codes=HTTPStatus.UNAUTHORIZED,
        )

        update_response = requests.put(
            url=f"{base_vws_url}/oauth2/clientcredentials/client-id/scopes",
            json=[],
            timeout=30,
        )
        assert_model_target_status(
            response=update_response,
            status_codes=HTTPStatus.UNAUTHORIZED,
        )


@pytest.mark.parametrize(
    argnames=("payload", "status_code"),
    argvalues=[
        (b'{"scope":[]}', HTTPStatus.FORBIDDEN),
        (b"[]", HTTPStatus.UNAUTHORIZED),
    ],
)
def test_invalid_token_scope(
    base_vws_url: str,
    payload: bytes,
    status_code: HTTPStatus,
) -> None:
    """A non-string scope or non-object payload has no usable
    scopes.
    """
    encoded_header = (
        base64.urlsafe_b64encode(
            s=b'{"alg":"mock"}',
        )
        .decode(encoding="ascii")
        .rstrip("=")
    )
    encoded_payload = (
        base64.urlsafe_b64encode(
            s=payload,
        )
        .decode(encoding="ascii")
        .rstrip("=")
    )
    token = f"{encoded_header}.{encoded_payload}.c2lnbmF0dXJl"
    with MockVWS(base_vws_url=base_vws_url):
        response = requests.get(
            url=f"{base_vws_url}/oauth2/clientcredentials",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        assert_model_target_status(
            response=response,
            status_codes=status_code,
        )


def test_client_credential_validation_errors(*, base_vws_url: str) -> None:
    """Credential creation and updates reject invalid request
    bodies.
    """
    with MockVWS(base_vws_url=base_vws_url):
        headers = {
            "Authorization": (
                f"Bearer {_management_token(base_vws_url=base_vws_url)}"
            ),
        }
        for content in (b"{", b'{"scopes":"scope"}', b'{"scopes":[1]}'):
            response = requests.post(
                url=f"{base_vws_url}/oauth2/clientcredentials",
                headers={**headers, "Content-Type": "application/json"},
                data=content,
                timeout=30,
            )
            assert_model_target_status(
                response=response,
                status_codes=HTTPStatus.BAD_REQUEST,
            )

        missing = requests.put(
            url=f"{base_vws_url}/oauth2/clientcredentials/missing/scopes",
            headers=headers,
            json=[],
            timeout=30,
        )
        assert_model_target_status(
            response=missing,
            status_codes=HTTPStatus.NOT_FOUND,
        )

        created = requests.post(
            url=f"{base_vws_url}/oauth2/clientcredentials",
            headers=headers,
            json={"scopes": []},
            timeout=30,
        )
        client_id = parse_response_json(response=created)["client_id"]
        assert isinstance(client_id, str)
        for content in (b"{", b'"scope"', b"[1]"):
            response = requests.put(
                url=(
                    f"{base_vws_url}/oauth2/clientcredentials/{client_id}/scopes"
                ),
                headers={**headers, "Content-Type": "application/json"},
                data=content,
                timeout=30,
            )
            assert_model_target_status(
                response=response,
                status_codes=HTTPStatus.BAD_REQUEST,
            )


def test_client_credential_limit(*, base_vws_url: str) -> None:
    """Credential creation rejects stores at their configured
    limit.
    """
    with MockVWS(base_vws_url=base_vws_url):
        headers = {
            "Authorization": (
                f"Bearer {_management_token(base_vws_url=base_vws_url)}"
            ),
        }
        credential_limit = 100
        for _ in range(credential_limit):
            created_response = requests.post(
                url=f"{base_vws_url}/oauth2/clientcredentials",
                headers=headers,
                json={"scopes": []},
                timeout=30,
            )
            assert_model_target_status(
                response=created_response,
                status_codes=HTTPStatus.CREATED,
            )

        response = requests.post(
            url=f"{base_vws_url}/oauth2/clientcredentials",
            headers=headers,
            json={"scopes": []},
            timeout=30,
        )
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.CONFLICT,
        )


def test_dataset_scope_and_shape_errors(*, base_vws_url: str) -> None:
    """State-based scope and less common model shapes are
    validated.
    """
    with MockVWS(base_vws_url=base_vws_url):
        state_based = {
            **UNAUTHENTICATED_DATASET_REQUEST,
            "models": [
                {
                    **MODEL,
                    "stateBasedConfigurationJsonString": (STATE_CONFIGURATION),
                },
            ],
        }
        forbidden = requests.post(
            url=f"{base_vws_url}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            json=state_based,
            timeout=30,
        )
        assert_model_target_status(
            response=forbidden,
            status_codes=HTTPStatus.FORBIDDEN,
        )

        invalid_view = requests.post(
            url=f"{base_vws_url}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            json={
                **UNAUTHENTICATED_DATASET_REQUEST,
                "models": [{**MODEL, "views": [1]}],
            },
            timeout=30,
        )
        assert_model_target_status(
            response=invalid_view,
            status_codes=HTTPStatus.BAD_REQUEST,
        )

        advanced_empty = requests.post(
            url=f"{base_vws_url}/modeltargets/advancedDatasets",
            headers={
                "Authorization": (
                    "Bearer eyJhbGciOiJtb2NrIn0."
                    "eyJzY29wZSI6Im1vZGVsdGFyZ2V0cy5hZHZhbmNlZG1vZGVs"
                    "dGFyZ2V0LmFsbCJ9.c2lnbmF0dXJl"
                ),
            },
            json={"name": "name", "targetSdk": "10.18", "models": []},
            timeout=30,
        )
        assert_model_target_status(
            response=advanced_empty,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
