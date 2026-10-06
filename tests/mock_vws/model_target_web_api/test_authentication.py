"""Tests for authentication through the Model Target Web API."""

import base64
import dataclasses
from http import HTTPStatus

import pytest
import requests

from mock_vws import MockVWS
from mock_vws._flask_server import target_manager as flask_target_manager
from tests.mock_vws.fixtures.model_target_prepared_requests import (
    credentials_for_backend,
)
from tests.mock_vws.fixtures.vuforia_backends import (
    VuforiaBackend,
)
from tests.mock_vws.model_target_web_api.assertions import (
    assert_model_target_error,
    assert_oauth2_error,
)
from tests.mock_vws.model_target_web_api.authentication import (
    MOCK_BEARER_TOKEN,
    VWS_HOST,
)
from tests.mock_vws.model_target_web_api.responses import parse_response_json
from tests.mock_vws.model_target_web_api.sample_data import (
    MODEL,
    STATE_CONFIGURATION,
    UNAUTHENTICATED_DATASET_REQUEST,
)
from tests.mock_vws.utils import ModelTargetEndpoint
from tests.mock_vws.utils.assertions import (
    assert_model_target_status,
)
from tests.mock_vws.utils.model_target_retries import model_target_get


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
class TestAuthentication:
    """Tests for Model Target Web API authentication.

    Bearer token concerns which apply to every Model Target endpoint are
    covered by ``TestAuthorizationHeader``, via the
    ``model_target_endpoint`` fixture.
    """

    @staticmethod
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
        auth: tuple[str, str] | None,
        data: dict[str, str],
        status_code: HTTPStatus,
        body: dict[str, str],
    ) -> None:
        """Invalid OAuth2 token requests are rejected."""
        response = requests.post(
            url=f"{VWS_HOST}/oauth2/token",
            auth=auth,
            data=data,
            timeout=30,
        )

        assert_oauth2_error(
            response=response,
            status_code=status_code,
            body=body,
        )

    @staticmethod
    def test_password_grant(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """A username and password can be exchanged for a scoped token."""
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.post(
            url=f"{VWS_HOST}/oauth2/token",
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

    @staticmethod
    def test_scoped_client_credentials_grant(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """A client credentials request accepts an explicit scope."""
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.post(
            url=f"{VWS_HOST}/oauth2/token",
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

    @staticmethod
    def test_insufficient_scope(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """A route rejects a token carrying only another route's scope."""
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        token_response = requests.post(
            url=f"{VWS_HOST}/oauth2/token",
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
            url=f"{VWS_HOST}/modeltargets/advancedDatasets",
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

    @staticmethod
    def test_client_credentials_management(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """Client credentials can be created, listed, updated and
        deleted.
        """
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        password_token_response = requests.post(
            url=f"{VWS_HOST}/oauth2/token",
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
            url=f"{VWS_HOST}/oauth2/clientcredentials",
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
                url=f"{VWS_HOST}/oauth2/clientcredentials",
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
                    f"{VWS_HOST}/oauth2/clientcredentials/{client_id}/scopes"
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
                url=f"{VWS_HOST}/oauth2/token",
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
                url=f"{VWS_HOST}/modeltargets/datasets",
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
                url=(f"{VWS_HOST}/oauth2/clientcredentials/{client_id}"),
                headers=headers,
                timeout=30,
            )
            assert_model_target_status(
                response=delete_response,
                status_codes=HTTPStatus.NO_CONTENT,
            )

        missing_client_id = "000000000000000000000"
        missing_response = requests.delete(
            url=(f"{VWS_HOST}/oauth2/clientcredentials/{missing_client_id}"),
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


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
class TestAuthorizationHeader:
    """Tests for the ``Authorization`` header on every Model Target
    endpoint.

    These mirror the cross-cutting tests which the ``endpoint`` fixture
    supports for the VWS and Query APIs. The Model Target Web API uses
    OAuth2 bearer tokens rather than HMAC signatures, so the VWS
    ``Authorization`` and ``Date`` header concerns do not apply to it,
    and it gets its own smaller set of concerns via the
    ``model_target_endpoint`` fixture. The OAuth2 token endpoint is not
    in that fixture because it takes HTTP Basic credentials rather than
    a bearer token.
    """

    @staticmethod
    def test_missing(
        *,
        model_target_endpoint: ModelTargetEndpoint,
    ) -> None:
        """An ``UNAUTHORIZED`` response is returned when no
        ``Authorization`` header is given.
        """
        response = model_target_endpoint.send()

        assert_model_target_error(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message="no Bearer token",
            target="jwt",
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("authorization", "message"),
        argvalues=[
            pytest.param("Basic abc", "no Bearer token", id="not-bearer"),
            pytest.param("Bearer ", "no Bearer token", id="blank"),
            pytest.param(
                "Bearer invalid-token",
                "Invalid JWT serialization: Missing dot delimiter(s)",
                id="malformed",
            ),
            pytest.param(
                "Bearer ..",
                "Invalid unsecured/JWS/JWE header: Invalid JSON object",
                id="invalid-header-json",
            ),
            pytest.param(
                "Bearer e30.e30.signature",
                'Missing "alg" in header JSON object',
                id="missing-algorithm",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJub25lIn0.e30.",
                (
                    "Unsecured (plain) JWTs are rejected, extend class to "
                    "handle"
                ),
                id="unsecured",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJSUzI1NiJ9.%.signature",
                "Payload of JWS object is not a valid JSON object",
                id="payload-not-base64",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJSUzI1NiJ9..signature",
                "Payload of JWS object is not a valid JSON object",
                id="blank-payload",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJSUzI1NiJ9.InZhbHVlIg.signature",
                "Payload of JWS object is not a valid JSON object",
                id="payload-not-json-object",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJSUzI1NiJ9.e30.",
                "The signature must not be empty",
                id="blank-signature",
            ),
            pytest.param(
                "Bearer eyJhbGciOiJSUzI1NiJ9.e30.%",
                "Signed JWT rejected: Invalid signature",
                id="signature-not-base64",
            ),
        ],
    )
    def test_invalid_bearer_token(
        *,
        model_target_endpoint: ModelTargetEndpoint,
        authorization: str,
        message: str,
    ) -> None:
        """Invalid bearer tokens are rejected."""
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers={
                **model_target_endpoint.headers,
                "Authorization": authorization,
            },
        )

        response = new_endpoint.send()

        assert_model_target_error(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message=message,
            target="jwt",
        )


class TestMockOnlyOAuth2EdgeCases:
    """Cover mock-only OAuth2 and validation error paths."""

    @staticmethod
    def _management_token() -> str:
        """Return a token which can manage client credentials."""
        response = requests.post(
            url=f"{VWS_HOST}/oauth2/token",
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

    @staticmethod
    def test_oauth2_grant_errors() -> None:
        """Invalid passwords and scopes are rejected."""
        with MockVWS():
            invalid_password = requests.post(
                url=f"{VWS_HOST}/oauth2/token",
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
                url=f"{VWS_HOST}/oauth2/token",
                auth=("client-id", "client-secret"),
                data={"scope": "not.a.scope"},
                timeout=30,
            )
            assert_model_target_status(
                response=invalid_scope,
                status_codes=HTTPStatus.BAD_REQUEST,
            )
            assert invalid_scope.json()["error"] == "invalid_scope"

    @staticmethod
    def test_client_credential_authentication_errors() -> None:
        """Credential-management routes enforce bearer-token validity and
        scope.
        """
        headers: list[dict[str, str]] = [
            {},
            {"Authorization": "Bearer malformed"},
            {"Authorization": "Bearer e30.e30.signature"},
            {"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
        ]
        with MockVWS():
            for request_headers in headers:
                response = requests.get(
                    url=f"{VWS_HOST}/oauth2/clientcredentials",
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
                url=f"{VWS_HOST}/oauth2/clientcredentials/client-id",
                timeout=30,
            )
            assert_model_target_status(
                response=delete_response,
                status_codes=HTTPStatus.UNAUTHORIZED,
            )

            create_response = requests.post(
                url=f"{VWS_HOST}/oauth2/clientcredentials",
                json={"scopes": []},
                timeout=30,
            )
            assert_model_target_status(
                response=create_response,
                status_codes=HTTPStatus.UNAUTHORIZED,
            )

            update_response = requests.put(
                url=f"{VWS_HOST}/oauth2/clientcredentials/client-id/scopes",
                json=[],
                timeout=30,
            )
            assert_model_target_status(
                response=update_response,
                status_codes=HTTPStatus.UNAUTHORIZED,
            )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("payload", "status_code"),
        argvalues=[
            (b'{"scope":[]}', HTTPStatus.FORBIDDEN),
            (b"[]", HTTPStatus.UNAUTHORIZED),
        ],
    )
    def test_invalid_token_scope(
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
        with MockVWS():
            response = requests.get(
                url=f"{VWS_HOST}/oauth2/clientcredentials",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            assert_model_target_status(
                response=response,
                status_codes=status_code,
            )

    @staticmethod
    def test_client_credential_validation_errors() -> None:
        """Credential creation and updates reject invalid request
        bodies.
        """
        with MockVWS():
            headers = {
                "Authorization": (
                    f"Bearer {TestMockOnlyOAuth2EdgeCases._management_token()}"
                ),
            }
            for content in (b"{", b'{"scopes":"scope"}', b'{"scopes":[1]}'):
                response = requests.post(
                    url=f"{VWS_HOST}/oauth2/clientcredentials",
                    headers={**headers, "Content-Type": "application/json"},
                    data=content,
                    timeout=30,
                )
                assert_model_target_status(
                    response=response,
                    status_codes=HTTPStatus.BAD_REQUEST,
                )

            missing = requests.put(
                url=f"{VWS_HOST}/oauth2/clientcredentials/missing/scopes",
                headers=headers,
                json=[],
                timeout=30,
            )
            assert_model_target_status(
                response=missing,
                status_codes=HTTPStatus.NOT_FOUND,
            )

            created = requests.post(
                url=f"{VWS_HOST}/oauth2/clientcredentials",
                headers=headers,
                json={"scopes": []},
                timeout=30,
            )
            client_id = parse_response_json(response=created)["client_id"]
            assert isinstance(client_id, str)
            for content in (b"{", b'"scope"', b"[1]"):
                response = requests.put(
                    url=(
                        f"{VWS_HOST}/oauth2/clientcredentials/"
                        f"{client_id}/scopes"
                    ),
                    headers={**headers, "Content-Type": "application/json"},
                    data=content,
                    timeout=30,
                )
                assert_model_target_status(
                    response=response,
                    status_codes=HTTPStatus.BAD_REQUEST,
                )

    @staticmethod
    def test_client_credential_limit() -> None:
        """Credential creation rejects stores at their configured
        limit.
        """
        with MockVWS():
            headers = {
                "Authorization": (
                    f"Bearer {TestMockOnlyOAuth2EdgeCases._management_token()}"
                ),
            }
            credential_limit = 100
            for _ in range(credential_limit):
                created_response = requests.post(
                    url=f"{VWS_HOST}/oauth2/clientcredentials",
                    headers=headers,
                    json={"scopes": []},
                    timeout=30,
                )
                assert_model_target_status(
                    response=created_response,
                    status_codes=HTTPStatus.CREATED,
                )

            response = requests.post(
                url=f"{VWS_HOST}/oauth2/clientcredentials",
                headers=headers,
                json={"scopes": []},
                timeout=30,
            )
            assert_model_target_status(
                response=response,
                status_codes=HTTPStatus.CONFLICT,
            )

    @staticmethod
    def test_dataset_scope_and_shape_errors() -> None:
        """State-based scope and less common model shapes are
        validated.
        """
        with MockVWS():
            state_based = {
                **UNAUTHENTICATED_DATASET_REQUEST,
                "models": [
                    {
                        **MODEL,
                        "stateBasedConfigurationJsonString": (
                            STATE_CONFIGURATION
                        ),
                    },
                ],
            }
            forbidden = requests.post(
                url=f"{VWS_HOST}/modeltargets/datasets",
                headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
                json=state_based,
                timeout=30,
            )
            assert_model_target_status(
                response=forbidden,
                status_codes=HTTPStatus.FORBIDDEN,
            )

            invalid_view = requests.post(
                url=f"{VWS_HOST}/modeltargets/datasets",
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
                url=f"{VWS_HOST}/modeltargets/advancedDatasets",
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

    @staticmethod
    def test_target_manager_missing_credential_delete() -> None:
        """The internal target manager returns 404 for an unknown
        credential.
        """
        response = flask_target_manager.remove_oauth2_client_credential(
            client_id="missing",
        )
        assert response.status_code == HTTPStatus.NOT_FOUND
