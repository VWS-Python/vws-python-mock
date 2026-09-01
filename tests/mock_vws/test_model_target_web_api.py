"""Verified fake tests for the Model Target Web API."""

# pyright: reportPrivateUsage=false

import base64
import dataclasses
import io
import json
import textwrap
import time
import zipfile
from collections.abc import Set as AbstractSet
from http import HTTPMethod, HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
import requests
from beartype import beartype
from vws.response import Response

from mock_vws import (
    MockVWS,
    ModelTargetGenerationFailure,
    _model_target_web_api,
)
from mock_vws._flask_server import target_manager as flask_target_manager
from mock_vws.model_target import ModelTargetDataset, ModelTargetDatasetType
from tests.mock_vws.fixtures.model_target_prepared_requests import (
    MODEL_TARGET_DATASET_UUID,
    credentials_for_backend,
    get_access_token,
)
from tests.mock_vws.fixtures.vuforia_backends import (
    VERIFY_MODEL_TARGET_SIGNING_OPTION,
    VuforiaBackend,
)
from tests.mock_vws.utils import ModelTargetEndpoint
from tests.mock_vws.utils.assertions import (
    assert_model_target_status,
    assert_valid_date_header,
)

_VWS_HOST = "https://vws.vuforia.com"
_MOCK_BEARER_TOKEN = (
    "eyJhbGciOiJtb2NrIn0."
    "eyJzY29wZSI6Im1vZGVsdGFyZ2V0cy5zdGFuZGFyZG1vZGVsdGFyZ2V0LmFsbCJ9."
    "c2lnbmF0dXJl"
)


_VIEW: dict[str, Any] = {
    "name": "view-name",
    "guideViewPosition": {
        "translation": [0, 0, 5],
        "rotation": [0, 0, 0, 1],
    },
}


@beartype
def _dataset_request(*, cad_data_url: str) -> dict[str, Any]:
    """Return a standard Model Target dataset request."""
    return {
        "name": f"dataset-{uuid4().hex}",
        "targetSdk": "10.18",
        "models": [
            {
                "name": "model-name",
                "cadDataUrl": cad_data_url,
                "views": [_VIEW],
            },
        ],
    }


@beartype
def _cad_data_blob() -> str:
    """Return a base64-encoded zipped model for inline CAD data."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(file=zip_buffer, mode="w") as zip_file:
        zip_file.writestr(
            zinfo_or_arcname="model.gltf",
            data=json.dumps(obj={"asset": {"version": "2.0"}}),
        )
    return base64.b64encode(s=zip_buffer.getvalue()).decode(encoding="ascii")


@beartype
def _blob_dataset_request() -> dict[str, Any]:
    """Return a standard dataset request with inline CAD data."""
    return {
        "name": f"dataset-{uuid4().hex}",
        "targetSdk": "10.18",
        "models": [
            {
                "name": "model-name",
                "cadDataBlob": _cad_data_blob(),
                "cadDataFormat": "ZIP",
                "views": [_VIEW],
            },
        ],
    }


_MODEL: dict[str, Any] = {
    "name": "model-name",
    "cadDataUrl": "https://example.com/model.glb",
    "views": [_VIEW],
}

_MODEL_WITHOUT_CAD_DATA: dict[str, Any] = {
    key: value for key, value in _MODEL.items() if key != "cadDataUrl"
}

_EMPTY_MODEL: dict[str, Any] = {}

_EMPTY_VIEW: dict[str, Any] = {}

_EMPTY_GUIDE_VIEW_POSITION: list[Any] = []

_EMPTY_GUIDE_VIEW_POSITION_OBJECT: dict[str, Any] = {}

_UNAUTHENTICATED_DATASET_REQUEST: dict[str, Any] = {
    "name": "dataset-name",
    "targetSdk": "10.18",
    "models": [_MODEL],
}

_STATE_CONFIGURATION = json.dumps(
    obj={
        "version": "1.0",
        "default_state": "assembled",
        "states": {
            "assembled": {"base_scene": 0},
            "disassembled": {"base_scene": 0},
        },
    },
)


@beartype
def _assert_oauth2_error(
    *,
    response: requests.Response,
    status_code: HTTPStatus,
    body: dict[str, str],
) -> None:
    """Assert an OAuth2 error response."""
    assert_model_target_status(
        response=response,
        status_codes=status_code,
    )
    assert response.json() == body


@beartype
def _assert_model_target_error(
    *,
    response: Response,
    status_code: HTTPStatus,
    code: str,
    message: str,
    target: str,
) -> None:
    """Assert a Model Target Web API error response with the legacy
    shape.
    """
    assert_model_target_status(
        response=response,
        status_codes=status_code,
    )
    assert json.loads(s=response.text) == {
        "error": {
            "code": code,
            "message": message,
            "target": target,
        },
    }


@beartype
def _assert_load_balancer_bad_request(*, response: Response) -> None:
    """Assert the ``BAD_REQUEST`` response from the load balancer.

    The load balancer in front of Vuforia rejects some requests before
    they reach an API, with an HTML error page rather than a Model Target
    Web API error body.
    """
    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.BAD_REQUEST,
    )
    assert_valid_date_header(response=response)
    expected_response_text = textwrap.dedent(
        text="""\
        <html>\r
        <head><title>400 Bad Request</title></head>\r
        <body>\r
        <center><h1>400 Bad Request</h1></center>\r
        </body>\r
        </html>\r
        """,
    )
    assert response.text == expected_response_text
    assert response.headers == {
        "Content-Length": str(object=len(response.text)),
        "Content-Type": "text/html",
        "Connection": "close",
        "Server": "awselb/2.0",
        "Date": response.headers["Date"],
    }


@beartype
def _assert_unknown_dataset(*, response: Response) -> None:
    """Assert a NOT_FOUND error for the unknown dataset UUID which the
    prepared requests use.

    The body-less Model Target endpoints ignore any request body, so a
    request with a valid bearer token and an unexpected or malformed body
    reaches the dataset lookup.
    """
    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.NOT_FOUND,
    )
    error = json.loads(s=response.text)["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message"] == (
        "Could not find a model-view database with uuid "
        f"{MODEL_TARGET_DATASET_UUID}"
    )
    # The user-id portion is per-account in real Vuforia, so check only
    # the stable prefix.
    assert error["target"].startswith("userId:")


@beartype
def _access_token_for_backend(*, backend: VuforiaBackend) -> str:
    """Return a valid access token for the chosen backend."""
    credentials = credentials_for_backend(backend=backend)
    return get_access_token(credentials=credentials, backend=backend)


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
            url=f"{_VWS_HOST}/oauth2/token",
            auth=auth,
            data=data,
            timeout=30,
        )

        _assert_oauth2_error(
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
            url=f"{_VWS_HOST}/oauth2/token",
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
            url=f"{_VWS_HOST}/oauth2/token",
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
            url=f"{_VWS_HOST}/oauth2/token",
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
            url=f"{_VWS_HOST}/modeltargets/advancedDatasets",
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
            url=f"{_VWS_HOST}/oauth2/token",
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
        client_id: str | None = None

        try:
            create_response = requests.post(
                url=f"{_VWS_HOST}/oauth2/clientcredentials",
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
            client_id = create_response.json()["client_id"]
            client_secret = create_response.json()["client_secret"]

            list_response = requests.get(
                url=f"{_VWS_HOST}/oauth2/clientcredentials",
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
                    f"{_VWS_HOST}/oauth2/clientcredentials/{client_id}/scopes"
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

            assert client_id is not None
            assert isinstance(client_secret, str)
            client_token_response = requests.post(
                url=f"{_VWS_HOST}/oauth2/token",
                auth=(client_id, client_secret),
                data={"grant_type": "client_credentials"},
                timeout=30,
            )
            assert_model_target_status(
                response=client_token_response,
                status_codes=HTTPStatus.OK,
            )
            client_access_token = client_token_response.json()["access_token"]
            insufficient_response = requests.post(
                url=f"{_VWS_HOST}/modeltargets/datasets",
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
            if client_id is not None:  # pragma: no branch
                delete_response = requests.delete(
                    url=(f"{_VWS_HOST}/oauth2/clientcredentials/{client_id}"),
                    headers=headers,
                    timeout=30,
                )
                assert_model_target_status(
                    response=delete_response,
                    status_codes=HTTPStatus.NO_CONTENT,
                )

        missing_client_id = "000000000000000000000"
        missing_response = requests.delete(
            url=(f"{_VWS_HOST}/oauth2/clientcredentials/{missing_client_id}"),
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

        _assert_model_target_error(
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

        _assert_model_target_error(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message=message,
            target="jwt",
        )


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
class TestContentLength:
    """Tests for the ``Content-Length`` header on every Model Target
    endpoint.

    These mirror the cross-cutting tests which the ``endpoint`` fixture
    supports for the VWS and Query APIs.

    A ``Content-Length`` header which is too large is not covered, for the
    same reason as it is not covered for the VWS API: real Vuforia waits
    for the body it was promised before timing out, which takes too long
    to run in a test.
    """

    @staticmethod
    def test_not_integer(
        *,
        model_target_endpoint: ModelTargetEndpoint,
    ) -> None:
        """A ``Content-Length`` header which is not an integer is rejected
        by the load balancer in front of Vuforia, before any bearer token
        is looked at.
        """
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers={
                **model_target_endpoint.headers,
                "Content-Length": "0.4",
            },
        )

        response = new_endpoint.send()

        _assert_load_balancer_bad_request(response=response)

    @staticmethod
    def test_not_integer_oauth2_token() -> None:
        """The OAuth2 token endpoint is behind the same load balancer.

        It is not in the ``model_target_endpoint`` fixture because it takes
        HTTP Basic credentials rather than a bearer token.
        """
        endpoint = ModelTargetEndpoint(
            base_url=_VWS_HOST,
            path_url="/oauth2/token",
            method=HTTPMethod.POST,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": "0.4",
            },
            data=b"grant_type=client_credentials",
            takes_json_body=False,
        )

        response = endpoint.send()

        _assert_load_balancer_bad_request(response=response)

    @staticmethod
    def test_too_small(
        *,
        model_target_endpoint: ModelTargetEndpoint,
    ) -> None:
        """A ``Content-Length`` header which is too small truncates the
        body, and the request is still rejected for having no bearer
        token.

        The Model Target Web API does not sign the request body, so unlike
        the VWS API it has no reason to notice the truncation before it
        looks at the ``Authorization`` header.
        """
        if not model_target_endpoint.takes_json_body:
            return

        content_length = len(model_target_endpoint.data) - 1
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers={
                **model_target_endpoint.headers,
                "Content-Length": str(object=content_length),
            },
        )

        response = new_endpoint.send()

        _assert_model_target_error(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            code="401",
            message="no Bearer token",
            target="jwt",
        )


class TestInvalidJson:
    """Tests for giving Model Target endpoints bodies which are not
    valid JSON objects.
    """

    @staticmethod
    @pytest.mark.parametrize(
        argnames="content_type",
        argvalues=[
            pytest.param(None, id="missing"),
            pytest.param("", id="empty"),
        ],
    )
    def test_wrong_content_type(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        model_target_endpoint: ModelTargetEndpoint,
        content_type: str | None,
    ) -> None:
        """Requests without a JSON content type are rejected with 415 by
        endpoints which read a body, and are unaffected elsewhere.
        """
        access_token = _access_token_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        new_headers = {
            **model_target_endpoint.headers,
            "Authorization": f"Bearer {access_token}",
        }
        if content_type is None:
            new_headers.pop("Content-Type", None)
        else:
            new_headers["Content-Type"] = content_type
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers=new_headers,
        )

        response = new_endpoint.send()

        if not model_target_endpoint.takes_json_body:
            _assert_unknown_dataset(response=response)
            return

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        )
        error = json.loads(s=response.text)["error"]
        assert error["code"] == "ERROR"
        assert error["message"] == (
            "Expecting text/json or application/json body"
        )
        assert "target" not in error

    @staticmethod
    def test_invalid_json(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        model_target_endpoint: ModelTargetEndpoint,
    ) -> None:
        """Malformed JSON bodies are rejected with 400 by endpoints which
        read a body, and are ignored elsewhere.
        """
        access_token = _access_token_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        content = b"{"
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers={
                **model_target_endpoint.headers,
                "Authorization": f"Bearer {access_token}",
                "Content-Length": str(object=len(content)),
            },
            data=content,
        )

        response = new_endpoint.send()

        if not model_target_endpoint.takes_json_body:
            _assert_unknown_dataset(response=response)
            return

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
        error = json.loads(s=response.text)["error"]
        assert error["code"] == "ERROR"
        assert error["message"].startswith("Invalid Json")
        assert "target" not in error

    @staticmethod
    def test_body_not_utf_8(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        model_target_endpoint: ModelTargetEndpoint,
    ) -> None:
        """Bodies which are not valid UTF-8 are rejected with 400 by
        endpoints which read a body, and are ignored elsewhere.
        """
        access_token = _access_token_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        content = b"\xff{}"
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers={
                **model_target_endpoint.headers,
                "Authorization": f"Bearer {access_token}",
                "Content-Length": str(object=len(content)),
            },
            data=content,
        )

        response = new_endpoint.send()

        if not model_target_endpoint.takes_json_body:
            _assert_unknown_dataset(response=response)
            return

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
        error = json.loads(s=response.text)["error"]
        assert error["code"] == "ERROR"
        assert error["message"].startswith("Invalid Json")
        assert "target" not in error

    @staticmethod
    @pytest.mark.parametrize(
        argnames="body",
        argvalues=[
            pytest.param("[]", id="array"),
            pytest.param('"dataset"', id="string"),
            pytest.param("1", id="number"),
            pytest.param("true", id="boolean"),
            pytest.param("null", id="null"),
        ],
    )
    def test_body_not_json_object(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        model_target_endpoint: ModelTargetEndpoint,
        body: str,
    ) -> None:
        """JSON bodies which are not objects are missing every field on
        endpoints which read a body, and are ignored elsewhere.
        """
        access_token = _access_token_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        content = body.encode(encoding="utf-8")
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers={
                **model_target_endpoint.headers,
                "Authorization": f"Bearer {access_token}",
                "Content-Length": str(object=len(content)),
            },
            data=content,
        )

        response = new_endpoint.send()

        if not model_target_endpoint.takes_json_body:
            _assert_unknown_dataset(response=response)
            return

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
        error = json.loads(s=response.text)["error"]
        assert error["code"] == "BAD_REQUEST"
        assert error["message"] == (
            f"Validation error for request {error['target']}"
        )
        actual_messages = {detail["message"] for detail in error["details"]}
        assert actual_messages == {
            "/models: element is required",
            "/name: element is required",
            "/targetSdk: element is required",
        }
        for detail in error["details"]:
            assert detail["code"] == "VALIDATION_ERROR"


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
class TestErrorResponses:
    """Verified fake tests for Model Target Web API error responses."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames="authorization",
        argvalues=[
            pytest.param("Basic not-base64!", id="invalid-base64"),
            pytest.param(
                (
                    "Basic "
                    + base64.b64encode(s=b"client-id-without-secret").decode()
                ),
                id="missing-separator",
            ),
        ],
    )
    def test_invalid_basic_auth_header(*, authorization: str) -> None:
        """Malformed OAuth2 Basic auth headers are rejected."""
        response = requests.post(
            url=f"{_VWS_HOST}/oauth2/token",
            headers={"Authorization": authorization},
            data={"grant_type": "client_credentials"},
            timeout=30,
        )

        _assert_oauth2_error(
            response=response,
            status_code=HTTPStatus.UNAUTHORIZED,
            body={
                "error": "invalid_request",
                "error_description": "Missing or invalid authorization header",
            },
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("body", "expected_messages"),
        argvalues=[
            pytest.param(
                {},
                {
                    "/models: element is required",
                    "/name: element is required",
                    "/targetSdk: element is required",
                },
                id="empty-body",
            ),
            pytest.param(
                {
                    "name": "dataset-name",
                    "targetSdk": "10.18",
                    "models": "model",
                },
                {"/models: error.expected.jsarray"},
                id="models-not-list",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [],
                },
                {"exactly one model should be provided"},
                id="standard-zero-models",
            ),
            pytest.param(
                {**_UNAUTHENTICATED_DATASET_REQUEST, "name": 1},
                {"/name: error.expected.jsstring"},
                id="name-not-string",
            ),
            pytest.param(
                {**_UNAUTHENTICATED_DATASET_REQUEST, "targetSdk": ["10.18"]},
                {"/targetSdk: error.expected.jsstring"},
                id="target-sdk-not-string",
            ),
            pytest.param(
                {"name": None, "targetSdk": None, "models": "model"},
                {
                    "/models: error.expected.jsarray",
                    "/name: error.expected.jsstring",
                    "/targetSdk: error.expected.jsstring",
                },
                id="multiple-type-errors",
            ),
            pytest.param(
                {**_UNAUTHENTICATED_DATASET_REQUEST, "models": ["model"]},
                {
                    "/models(0)/name: element is required",
                    "/models(0)/views: element is required",
                },
                id="model-not-object",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        *_UNAUTHENTICATED_DATASET_REQUEST["models"],
                        "model",
                    ],
                },
                {
                    "/models(1)/name: element is required",
                    "/models(1)/views: element is required",
                },
                id="second-model-not-object",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [_EMPTY_MODEL],
                },
                {
                    "/models(0)/name: element is required",
                    "/models(0)/views: element is required",
                },
                id="model-missing-fields",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [_MODEL_WITHOUT_CAD_DATA],
                },
                {
                    (
                        "model 'model-name' is invalid. One of `cadDataBlob`, "
                        "`cadDataUrl`, `cadDataUuid` need to be provided"
                    ),
                },
                id="model-without-cad-data",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "cadDataBlob": "ZmFrZQ==",
                            "cadDataFormat": "ZIP",
                        },
                    ],
                },
                {
                    (
                        "model 'model-name' is invalid. Only one of "
                        "`cadDataBlob`, `cadDataUrl`, `cadDataUuid` need to "
                        "be provided"
                    ),
                },
                id="model-with-both-cad-data-sources",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "cadDataUrl": 1,
                        },
                    ],
                },
                {"/models(0)/cadDataUrl: error.expected.jsstring"},
                id="model-cad-data-url-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL_WITHOUT_CAD_DATA,
                            "cadDataBlob": 1,
                            "cadDataFormat": "ZIP",
                        },
                    ],
                },
                {"/models(0)/cadDataBlob: error.expected.jsstring"},
                id="model-cad-data-blob-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "cadDataFormat": 1}],
                },
                {"/models(0)/cadDataFormat: error.expected.jsstring"},
                id="model-cad-data-format-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "cadDataFormat": "gltf"}],
                },
                {
                    (
                        "Unrecognized cadDataFormat 'GLTF'.  Allowed values "
                        "are: ZIP, GLB, DRC_GLB, DRC_GLTF, DAE, FBX, IGES, "
                        "OBJ, PVS, PVZ, STL, VRML, or specify no "
                        "cadDataFormat to auto-detect GLB and zipped glTFs."
                    ),
                },
                id="model-cad-data-format-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "name": None}],
                },
                {"/models(0)/name: error.expected.jsstring"},
                id="model-name-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "simplify": 1}],
                },
                {"/models(0)/simplify: error.expected.jsstring"},
                id="model-simplify-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "simplify": "sometimes"}],
                },
                {
                    (
                        "invalid simplify. Should be one of 'never', "
                        "'always', 'auto'. You provided 'Some(sometimes)'"
                    ),
                },
                id="model-simplify-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "automaticColoring": "sometimes"}],
                },
                {
                    (
                        "invalid automaticColoring. Should be one of 'never', "
                        "'always', 'auto'. You provided 'sometimes'"
                    ),
                },
                id="model-automatic-coloring-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "motionHint": "still"}],
                },
                {
                    (
                        "`motionHint` and `trackingMode` are no longer "
                        "supported when using `targetsSdk` 10.9 or later. "
                        "Please use the `optimizeTrackingFor` setting instead."
                    ),
                },
                id="model-motion-hint-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "optimizeTrackingFor": "cars"}],
                },
                {
                    (
                        "`optimizeTrackingFor` must be one of "
                        "default,low_feature_objects,ar_controller"
                    ),
                },
                id="model-optimize-tracking-for-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "trackingMode": "boat"}],
                },
                {
                    (
                        "`motionHint` and `trackingMode` are no longer "
                        "supported when using `targetsSdk` 10.9 or later. "
                        "Please use the `optimizeTrackingFor` setting instead."
                    ),
                },
                id="model-tracking-mode-not-in-enum",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "motionHint": "still",
                            "simplify": "sometimes",
                        },
                    ],
                },
                {
                    (
                        "`motionHint` and `trackingMode` are no longer "
                        "supported when using `targetsSdk` 10.9 or later. "
                        "Please use the `optimizeTrackingFor` setting instead."
                    ),
                    (
                        "invalid simplify. Should be one of 'never', "
                        "'always', 'auto'. You provided 'Some(sometimes)'"
                    ),
                },
                id="model-multiple-enum-errors",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "views": "view-name"}],
                },
                {"/models(0)/views: error.expected.jsarray"},
                id="model-views-not-array",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "views": ["view-name"]}],
                },
                {"/models(0)/views(0)/name: element is required"},
                id="view-not-object",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "views": [_EMPTY_VIEW]}],
                },
                {"/models(0)/views(0)/name: element is required"},
                id="view-missing-fields",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {**_MODEL, "views": [{**_VIEW, "name": 1}]},
                    ],
                },
                {"/models(0)/views(0)/name: error.expected.jsstring"},
                id="view-name-not-string",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                _VIEW,
                                {
                                    **_VIEW,
                                    "guideViewPosition": (
                                        _EMPTY_GUIDE_VIEW_POSITION
                                    ),
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(1)/guideViewPosition: "
                        "error.expected.jsobject"
                    ),
                },
                id="view-guide-view-position-not-object",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                {
                                    **_VIEW,
                                    "guideViewPosition": (
                                        _EMPTY_GUIDE_VIEW_POSITION_OBJECT
                                    ),
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(0)/guideViewPosition/rotation: "
                        "element is required"
                    ),
                    (
                        "/models(0)/views(0)/guideViewPosition/translation: "
                        "element is required"
                    ),
                },
                id="guide-view-position-missing-fields",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                {
                                    **_VIEW,
                                    "guideViewPosition": {
                                        "rotation": "0,0,0,1",
                                        "translation": [0, 0, 5],
                                    },
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(0)/guideViewPosition/rotation: "
                        "error.expected.jsarray"
                    ),
                },
                id="guide-view-position-rotation-not-array",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                {
                                    **_VIEW,
                                    "guideViewPosition": {
                                        "rotation": [0, 0, 0, 1],
                                        "translation": 5,
                                    },
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(0)/guideViewPosition/translation: "
                        "error.expected.jsarray"
                    ),
                },
                id="guide-view-position-translation-not-array",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                {
                                    **_VIEW,
                                    "guideViewPosition": {
                                        "rotation": [0, "0", 0, 1],
                                        "translation": [0, 0, 5],
                                    },
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(0)/guideViewPosition/rotation(1): "
                        "error.expected.jsnumber"
                    ),
                },
                id="guide-view-position-rotation-element-not-number",
            ),
            pytest.param(
                {
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [
                        {
                            **_MODEL,
                            "views": [
                                {
                                    **_VIEW,
                                    "guideViewPosition": {
                                        "rotation": [0, 0, 0, 1],
                                        "translation": [0, 0, True],
                                    },
                                },
                            ],
                        },
                    ],
                },
                {
                    (
                        "/models(0)/views(0)/guideViewPosition/"
                        "translation(2): error.expected.jsnumber"
                    ),
                },
                id="guide-view-position-translation-element-not-number",
            ),
        ],
    )
    def test_invalid_dataset_request(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        body: dict[str, object],
        expected_messages: set[str],
    ) -> None:
        """Invalid standard dataset creation requests are rejected."""
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.post(
            url=f"{_VWS_HOST}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
            timeout=30,
        )

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
        error = response.json()["error"]
        assert error["code"] == "BAD_REQUEST"
        assert error["message"] == (
            f"Validation error for request {error['target']}"
        )
        actual_messages = {detail["message"] for detail in error["details"]}
        assert actual_messages == expected_messages
        for detail in error["details"]:
            assert detail["code"] == "VALIDATION_ERROR"

    @staticmethod
    def test_advanced_model_count_exceeds_limit(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """Advanced datasets reject more than 20 uniquely named models."""
        models = [{**_MODEL, "name": f"model-{index}"} for index in range(21)]
        # Include a duplicate to verify the two validation details which real
        # Vuforia returns together for this request.
        models[-1]["name"] = models[0]["name"]
        body = {**_UNAUTHENTICATED_DATASET_REQUEST, "models": models}
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.post(
            url=f"{_VWS_HOST}/modeltargets/advancedDatasets",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
            timeout=30,
        )

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
        error = response.json()["error"]
        assert error["code"] == "BAD_REQUEST"
        assert {detail["message"] for detail in error["details"]} == {
            "names of models must be unique within a Target.",
            "total number of models must be maximum 20",
        }
        assert all(
            detail["code"] == "VALIDATION_ERROR" for detail in error["details"]
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("method", "path"),
        argvalues=[
            pytest.param(
                HTTPMethod.GET,
                f"/modeltargets/datasets/{MODEL_TARGET_DATASET_UUID}/status",
                id="status",
            ),
            pytest.param(
                HTTPMethod.GET,
                f"/modeltargets/datasets/{MODEL_TARGET_DATASET_UUID}/dataset",
                id="download",
            ),
            pytest.param(
                HTTPMethod.DELETE,
                f"/modeltargets/datasets/{MODEL_TARGET_DATASET_UUID}",
                id="delete",
            ),
        ],
    )
    def test_unknown_dataset(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        method: HTTPMethod,
        path: str,
    ) -> None:
        """Unknown datasets are rejected with a NOT_FOUND error."""
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.request(
            method=method,
            url=f"{_VWS_HOST}{path}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.NOT_FOUND,
        )
        error = response.json()["error"]
        assert error["code"] == "NOT_FOUND"
        assert error["message"] == (
            "Could not find a model-view database with uuid "
            f"{MODEL_TARGET_DATASET_UUID}"
        )
        # The user-id portion is per-account in real Vuforia, so check only
        # the stable prefix.
        assert error["target"].startswith("userId:")


# Creating an advanced dataset with a state-based configuration is a
# "signed" request: the real Vuforia signs the trained dataset, and each
# signing consumes the account's Model Target training allowance.  The
# allowance is tiny (roughly 20 signings, under ten CI runs' worth), it
# is shared by every CI job and every concurrent run, and it cannot be
# raised or reset by us.  Verifying this behavior on every run therefore
# burns the whole allowance within hours and then turns every CI run red
# with ``TRAINING_ALLOWANCE_EXCEEDED`` - which is exactly what happened
# when it ran unconditionally.  The equivalent unsigned requests (a
# standard dataset, or an advanced dataset without a state-based
# configuration) consume nothing and stay verified on every run.
_SIGNED_REQUEST_SKIP_REASON = (
    "Signed Model Target requests consume the real Vuforia account's "
    "small, shared, non-resettable training allowance, so they are not "
    "verified against the real Vuforia by default. Pass "
    f"{VERIFY_MODEL_TARGET_SIGNING_OPTION} to verify them, for example "
    "after the allowance has recovered. The mock backends always run "
    "this test."
)


class TestStateBasedDatasets:
    """Verified fake tests for State-Based Model Targets.

    The advanced (signed) cases are verified against the real Vuforia
    only when ``--verify-model-target-signing`` is given: see
    ``_SIGNED_REQUEST_SKIP_REASON``.
    """

    @staticmethod
    @pytest.mark.parametrize(
        argnames="dataset_path",
        argvalues=[
            pytest.param("/modeltargets/datasets", id="standard"),
            pytest.param(
                "/modeltargets/advancedDatasets",
                id="advanced",
            ),
        ],
    )
    @pytest.mark.parametrize(
        argnames="view_updates",
        argvalues=[
            pytest.param({}, id="all-states"),
            pytest.param(
                {"states": ["assembled"]},
                id="selected-states",
            ),
        ],
    )
    def test_state_based_dataset(
        *,
        request: pytest.FixtureRequest,
        verify_model_target_mock_vuforia: VuforiaBackend,
        dataset_path: str,
        view_updates: dict[str, object],
    ) -> None:
        """State-Based Model Target fields survive a dataset round
        trip.
        """
        if (
            verify_model_target_mock_vuforia is VuforiaBackend.REAL
            and dataset_path == "/modeltargets/advancedDatasets"
            and not request.config.getoption(
                name=VERIFY_MODEL_TARGET_SIGNING_OPTION,
            )
        ):
            pytest.skip(reason=_SIGNED_REQUEST_SKIP_REASON)
        body = {
            **_UNAUTHENTICATED_DATASET_REQUEST,
            "models": [
                {
                    **_MODEL,
                    "stateBasedConfigurationJsonString": (
                        _STATE_CONFIGURATION
                    ),
                    "views": [{**_VIEW, **view_updates}],
                },
            ],
        }
        access_token = _access_token_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        headers = {"Authorization": f"Bearer {access_token}"}
        create_response = requests.post(
            url=f"{_VWS_HOST}{dataset_path}",
            headers=headers,
            json=body,
            timeout=30,
        )

        assert_model_target_status(
            response=create_response,
            status_codes=HTTPStatus.CREATED,
        )
        dataset_uuid = create_response.json()["uuid"]
        delete_response = requests.delete(
            url=f"{_VWS_HOST}{dataset_path}/{dataset_uuid}",
            headers=headers,
            timeout=30,
        )
        assert_model_target_status(
            response=delete_response,
            status_codes=HTTPStatus.OK,
        )

    @staticmethod
    def test_view_states_are_a_subset(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """A view cannot select a state absent from the configuration."""
        body = {
            **_UNAUTHENTICATED_DATASET_REQUEST,
            "models": [
                {
                    **_MODEL,
                    "stateBasedConfigurationJsonString": (
                        _STATE_CONFIGURATION
                    ),
                    "views": [{**_VIEW, "states": ["unknown"]}],
                },
            ],
        }
        access_token = _access_token_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        response = requests.post(
            url=f"{_VWS_HOST}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
            timeout=30,
        )

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
        error = response.json()["error"]
        assert error["code"] == "BAD_REQUEST"
        assert [detail["message"] for detail in error["details"]] == [
            "states in entrypoint view-name' must be a subset of all states",
        ]
        assert error["details"][0]["code"] == "VALIDATION_ERROR"


class TestAdditionalBehaviors:
    """Additional verified and mock-only Model Target behaviors."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("model_updates", "view_updates", "expected_message"),
        argvalues=[
            pytest.param(
                {"stateBasedConfigurationJsonString": 1},
                {},
                (
                    "/models(0)/stateBasedConfigurationJsonString: "
                    "error.expected.jsstring"
                ),
                id="configuration-not-string",
            ),
            pytest.param(
                {"stateBasedConfigurationJsonString": "{"},
                {},
                (
                    "/models(0)/stateBasedConfigurationJsonString: "
                    "error.expected.validjson"
                ),
                id="configuration-not-json",
            ),
            pytest.param(
                {"stateBasedConfigurationJsonString": "{}"},
                {},
                (
                    "/models(0)/stateBasedConfigurationJsonString/states: "
                    "error.expected.jsobject"
                ),
                id="configuration-states-not-object",
            ),
            pytest.param(
                {"stateBasedConfigurationJsonString": "[]"},
                {},
                (
                    "/models(0)/stateBasedConfigurationJsonString/states: "
                    "error.expected.jsobject"
                ),
                id="configuration-not-object",
            ),
            pytest.param(
                {"stateBasedConfigurationJsonString": _STATE_CONFIGURATION},
                {"states": "assembled"},
                "/models(0)/views(0)/states: error.expected.jsarray",
                id="view-states-not-array",
            ),
            pytest.param(
                {"stateBasedConfigurationJsonString": _STATE_CONFIGURATION},
                {"states": ["assembled", 1]},
                ("/models(0)/views(0)/states(1): error.expected.jsstring"),
                id="view-state-not-string",
            ),
            pytest.param(
                {},
                {"states": ["assembled"]},
                (
                    "/models(0)/stateBasedConfigurationJsonString: element "
                    "is required when view states are given"
                ),
                id="view-states-without-configuration",
            ),
        ],
    )
    def test_invalid_state_based_dataset(
        *,
        model_target_mock_only_vuforia: VuforiaBackend,
        model_updates: dict[str, object],
        view_updates: dict[str, object],
        expected_message: str,
    ) -> None:
        """Invalid State-Based Model Target fields are rejected."""
        body = {
            **_UNAUTHENTICATED_DATASET_REQUEST,
            "models": [
                {
                    **_MODEL,
                    **model_updates,
                    "views": [{**_VIEW, **view_updates}],
                },
            ],
        }
        access_token = _access_token_for_backend(
            backend=model_target_mock_only_vuforia,
        )
        response = requests.post(
            url=f"{_VWS_HOST}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
            timeout=30,
        )

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
        error = response.json()["error"]
        assert error["code"] == "BAD_REQUEST"
        assert [detail["message"] for detail in error["details"]] == [
            expected_message,
        ]
        assert error["details"][0]["code"] == "VALIDATION_ERROR"

    @staticmethod
    def test_advanced_realistic_appearance_not_in_enum(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """Advanced dataset requests with a ``realisticAppearance`` value
        outside the documented enumeration are rejected.

        The Model Target OpenAPI specification documents
        ``realisticAppearance`` as a model field for advanced datasets
        only.
        """
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        body = {
            **_UNAUTHENTICATED_DATASET_REQUEST,
            "models": [
                {
                    **_MODEL,
                    "cadDataUrl": credentials.cad_data_url,
                    "realisticAppearance": "yes",
                },
            ],
        }
        access_token = get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        advanced_response = requests.post(
            url=f"{_VWS_HOST}/modeltargets/advancedDatasets",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
            timeout=30,
        )

        assert_model_target_status(
            response=advanced_response,
            status_codes=HTTPStatus.BAD_REQUEST,
        )
        error = advanced_response.json()["error"]
        assert error["code"] == "BAD_REQUEST"
        assert [detail["message"] for detail in error["details"]] == [
            '`realisticAppearance` must be one of "true", "false", "auto".` ',
        ]
        assert error["details"][0]["code"] == "VALIDATION_ERROR"

    @staticmethod
    def test_oauth2_token_body_not_utf_8(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """An OAuth2 token request with a body which is not valid UTF-8 is
        treated as one which does not name a grant type.

        Real Vuforia also treats a body that cannot be decoded as an empty
        form.
        """
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )

        response = requests.post(
            url=f"{_VWS_HOST}/oauth2/token",
            auth=(credentials.client_id, credentials.client_secret),
            data=b"\xff",
            timeout=30,
        )

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.OK,
        )
        assert response.json()["token_type"] == "bearer"

    @staticmethod
    def test_processing_dataset_cannot_be_downloaded() -> None:
        """A dataset cannot be downloaded while it is still processing.

        Mock-only because exercising this against real Vuforia would require
        creating a dataset on every test run; the mock lets us drive the
        processing window deterministically.
        """
        with MockVWS(processing_time_seconds=60):
            create_response = requests.post(
                url=f"{_VWS_HOST}/modeltargets/datasets",
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                json=_UNAUTHENTICATED_DATASET_REQUEST,
                timeout=30,
            )
            dataset_uuid = create_response.json()["uuid"]
            response = requests.get(
                url=(
                    f"{_VWS_HOST}/modeltargets/datasets/{dataset_uuid}/dataset"
                ),
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                timeout=30,
            )

        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
        error = response.json()["error"]
        assert error["code"] == "UNSUPPORTED_STATE"
        assert error["message"] == (
            f"Training status for dataset {dataset_uuid} is "
            "not-started != done"
        )
        assert error["target"] == dataset_uuid

    @staticmethod
    def test_failed_dataset_cannot_be_downloaded() -> None:
        """A dataset which failed generation cannot be downloaded, and the
        error reports the failed training status rather than the
        ``not-started`` status which a still-processing dataset reports.

        Mock-only because a generation failure cannot be provoked on demand
        against real Vuforia, so the training status name it reports for a
        failed dataset has not been observed.
        """
        failure = ModelTargetGenerationFailure(message="CAD model is invalid")
        with MockVWS(
            processing_time_seconds=0,
            model_target_generation_failure=failure,
        ):
            create_response = requests.post(
                url=f"{_VWS_HOST}/modeltargets/datasets",
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                json=_UNAUTHENTICATED_DATASET_REQUEST,
                timeout=30,
            )
            dataset_uuid = create_response.json()["uuid"]
            status_response = requests.get(
                url=f"{_VWS_HOST}/modeltargets/datasets/{dataset_uuid}/status",
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                timeout=30,
            )
            response = requests.get(
                url=(
                    f"{_VWS_HOST}/modeltargets/datasets/{dataset_uuid}/dataset"
                ),
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                timeout=30,
            )

        assert status_response.json()["status"] == "failed"
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
        error = response.json()["error"]
        assert error["code"] == "UNSUPPORTED_STATE"
        assert error["message"] == (
            f"Training status for dataset {dataset_uuid} is failed != done"
        )
        assert error["target"] == dataset_uuid

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("created_path", "other_path"),
        argvalues=[
            pytest.param(
                "/modeltargets/datasets",
                "/modeltargets/advancedDatasets",
                id="standard-dataset-via-advanced-routes",
            ),
            pytest.param(
                "/modeltargets/advancedDatasets",
                "/modeltargets/datasets",
                id="advanced-dataset-via-standard-routes",
            ),
        ],
    )
    def test_dataset_is_visible_to_the_other_dataset_type(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        created_path: str,
        other_path: str,
    ) -> None:
        """Standard and advanced routes share datasets by UUID."""
        access_token = _access_token_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        headers = {"Authorization": f"Bearer {access_token}"}
        dataset_uuid: str | None = None
        try:
            create_response = requests.post(
                url=f"{_VWS_HOST}{created_path}",
                headers=headers,
                json=_dataset_request(
                    cad_data_url=credentials_for_backend(
                        backend=verify_model_target_mock_vuforia,
                    ).cad_data_url,
                ),
                timeout=30,
            )
            assert_model_target_status(
                response=create_response,
                status_codes=HTTPStatus.CREATED,
            )
            dataset_uuid = create_response.json()["uuid"]

            other_status_response = requests.get(
                url=f"{_VWS_HOST}{other_path}/{dataset_uuid}/status",
                headers=headers,
                timeout=30,
            )
            other_delete_response = requests.delete(
                url=f"{_VWS_HOST}{other_path}/{dataset_uuid}",
                headers=headers,
                timeout=30,
            )
            own_status_response = requests.get(
                url=(
                    f"{_VWS_HOST}{created_path}/"
                    f"{create_response.json()['uuid']}/status"
                ),
                headers=headers,
                timeout=30,
            )
        finally:
            if dataset_uuid is not None:  # pragma: no branch
                delete_response = requests.delete(
                    url=f"{_VWS_HOST}{created_path}/{dataset_uuid}",
                    headers=headers,
                    timeout=30,
                )
                assert_model_target_status(
                    response=delete_response,
                    status_codes={
                        HTTPStatus.OK,
                        HTTPStatus.NO_CONTENT,
                    },
                )

        assert_model_target_status(
            response=other_status_response,
            status_codes=HTTPStatus.OK,
        )
        assert_model_target_status(
            response=other_delete_response,
            status_codes={
                HTTPStatus.OK,
                HTTPStatus.NO_CONTENT,
            },
        )
        assert_model_target_status(
            response=own_status_response,
            status_codes=HTTPStatus.OK,
        )


class TestStandardDataset:
    """Tests for standard Model Target datasets."""

    @staticmethod
    def test_create_status_and_delete(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """A standard dataset works through the shared advanced routes.

        Standard generation is fast enough for verified CI coverage. Real
        Vuforia exposes its completed artifact through both route families,
        so this also verifies the advanced status and download endpoints.
        """
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        headers = {"Authorization": f"Bearer {access_token}"}
        dataset_uuid: str | None = None

        try:
            create_response = requests.post(
                url=f"{_VWS_HOST}/modeltargets/datasets",
                headers=headers,
                json=_dataset_request(cad_data_url=credentials.cad_data_url),
                timeout=30,
            )

            assert_model_target_status(
                response=create_response,
                status_codes=HTTPStatus.CREATED,
            )
            create_response_json: dict[str, Any] = json.loads(
                s=create_response.text,
            )
            dataset_uuid_value = create_response_json["uuid"]
            assert isinstance(dataset_uuid_value, str)
            dataset_uuid = dataset_uuid_value

            status_response = requests.get(
                url=(
                    f"{_VWS_HOST}/modeltargets/advancedDatasets/"
                    f"{dataset_uuid}/status"
                ),
                headers=headers,
                timeout=30,
            )

            assert_model_target_status(
                response=status_response,
                status_codes=HTTPStatus.OK,
            )
            status_response_json: dict[str, Any] = json.loads(
                s=status_response.text,
            )
            assert status_response_json["status"] in {
                "processing",
                "done",
                "failed",
            }
            assert isinstance(status_response_json["createdAt"], str)

            deadline = time.monotonic() + 60
            while (
                status_response_json["status"] == "processing"
                and time.monotonic() < deadline
            ):
                time.sleep(1)
                status_response = requests.get(
                    url=(
                        f"{_VWS_HOST}/modeltargets/advancedDatasets/"
                        f"{dataset_uuid}/status"
                    ),
                    headers=headers,
                    timeout=30,
                )
                assert_model_target_status(
                    response=status_response,
                    status_codes=HTTPStatus.OK,
                )
                status_response_json = status_response.json()

            assert status_response_json["status"] == "done"
            assert isinstance(status_response_json["completedAt"], str)
            assert set(status_response_json) == {
                "completedAt",
                "createdAt",
                "status",
                "uuid",
            }

            download_response = requests.get(
                url=(
                    f"{_VWS_HOST}/modeltargets/advancedDatasets/"
                    f"{dataset_uuid}/dataset"
                ),
                headers=headers,
                timeout=30,
            )
            assert_model_target_status(
                response=download_response,
                status_codes=HTTPStatus.OK,
            )
            assert download_response.headers["Content-Type"] == (
                "application/zip"
            )
            assert download_response.headers["Content-Disposition"] == (
                "attachment; filename=full-dataset.zip"
            )
            with zipfile.ZipFile(
                file=io.BytesIO(initial_bytes=download_response.content),
            ) as archive:
                assert archive.namelist() == ["MTDataset.dat", "MTDataset.xml"]
        finally:
            if dataset_uuid is not None:  # pragma: no branch
                delete_response = requests.delete(
                    url=f"{_VWS_HOST}/modeltargets/datasets/{dataset_uuid}",
                    headers=headers,
                    timeout=30,
                )
                assert_model_target_status(
                    response=delete_response,
                    status_codes={
                        HTTPStatus.OK,
                        HTTPStatus.NO_CONTENT,
                    },
                )

    @staticmethod
    def test_create_with_cad_data_blob(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
    ) -> None:
        """A dataset can be created with inline CAD data."""
        credentials = credentials_for_backend(
            backend=verify_model_target_mock_vuforia,
        )
        access_token = get_access_token(
            credentials=credentials,
            backend=verify_model_target_mock_vuforia,
        )
        headers = {"Authorization": f"Bearer {access_token}"}

        create_response = requests.post(
            url=f"{_VWS_HOST}/modeltargets/datasets",
            headers=headers,
            json=_blob_dataset_request(),
            timeout=30,
        )

        assert_model_target_status(
            response=create_response,
            status_codes=HTTPStatus.CREATED,
        )
        create_response_json: dict[str, Any] = json.loads(
            s=create_response.text,
        )
        dataset_uuid = create_response_json["uuid"]
        assert isinstance(dataset_uuid, str)

        # There is nothing to assert between creating and deleting the
        # dataset, so the delete does not need a ``finally`` block to avoid
        # leaving a dataset behind on real Vuforia.
        delete_response = requests.delete(
            url=f"{_VWS_HOST}/modeltargets/datasets/{dataset_uuid}",
            headers=headers,
            timeout=30,
        )
        assert_model_target_status(
            response=delete_response,
            status_codes={
                HTTPStatus.OK,
                HTTPStatus.NO_CONTENT,
            },
        )


class TestModelTargetDatasetStatus:
    """Tests for Model Target dataset status response bodies."""

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("processing_time_seconds", "status", "time_field"),
        argvalues=[
            pytest.param(3600.0, "processing", "eta", id="processing"),
            pytest.param(0.0, "done", "completedAt", id="done"),
        ],
    )
    def test_status_uses_matching_time_field(
        *,
        processing_time_seconds: float,
        status: str,
        time_field: str,
    ) -> None:
        """Each status includes only its matching timestamp field."""
        dataset = ModelTargetDataset(
            request_body={},
            dataset_type=ModelTargetDatasetType.STANDARD,
            processing_time_seconds=processing_time_seconds,
            generation_failure=None,
            generation_warning=None,
            uuid_="dataset-uuid",
        )

        body = dataset.status_body()

        assert body["status"] == status
        assert body["uuid"] == "dataset-uuid"
        assert {"eta", "completedAt"} & body.keys() == {time_field}


class TestMockOnlyOAuth2EdgeCases:
    """Cover mock-only OAuth2 and validation error paths."""

    @staticmethod
    def _management_token() -> str:
        """Return a token which can manage client credentials."""
        response = requests.post(
            url=f"{_VWS_HOST}/oauth2/token",
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
                url=f"{_VWS_HOST}/oauth2/token",
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
                url=f"{_VWS_HOST}/oauth2/token",
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
        headers = [
            {},
            {"Authorization": "Bearer malformed"},
            {"Authorization": "Bearer e30.e30.signature"},
            {"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
        ]
        with MockVWS():
            for request_headers in headers:
                response = requests.get(
                    url=f"{_VWS_HOST}/oauth2/clientcredentials",
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
                url=f"{_VWS_HOST}/oauth2/clientcredentials/client-id",
                timeout=30,
            )
            assert_model_target_status(
                response=delete_response,
                status_codes=HTTPStatus.UNAUTHORIZED,
            )

            create_response = requests.post(
                url=f"{_VWS_HOST}/oauth2/clientcredentials",
                json={"scopes": []},
                timeout=30,
            )
            assert_model_target_status(
                response=create_response,
                status_codes=HTTPStatus.UNAUTHORIZED,
            )

            update_response = requests.put(
                url=f"{_VWS_HOST}/oauth2/clientcredentials/client-id/scopes",
                json=[],
                timeout=30,
            )
            assert_model_target_status(
                response=update_response,
                status_codes=HTTPStatus.UNAUTHORIZED,
            )

    @staticmethod
    def test_non_string_token_scope() -> None:
        """A token with a non-string scope has no usable scopes."""
        encoded_header = (
            base64.urlsafe_b64encode(
                s=b'{"alg":"mock"}',
            )
            .decode(encoding="ascii")
            .rstrip("=")
        )
        encoded_payload = (
            base64.urlsafe_b64encode(
                s=b'{"scope":[]}',
            )
            .decode(encoding="ascii")
            .rstrip("=")
        )
        token = f"{encoded_header}.{encoded_payload}.c2lnbmF0dXJl"
        with MockVWS():
            response = requests.get(
                url=f"{_VWS_HOST}/oauth2/clientcredentials",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            assert_model_target_status(
                response=response,
                status_codes=HTTPStatus.FORBIDDEN,
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
                    url=f"{_VWS_HOST}/oauth2/clientcredentials",
                    headers={**headers, "Content-Type": "application/json"},
                    data=content,
                    timeout=30,
                )
                assert_model_target_status(
                    response=response,
                    status_codes=HTTPStatus.BAD_REQUEST,
                )

            missing = requests.put(
                url=f"{_VWS_HOST}/oauth2/clientcredentials/missing/scopes",
                headers=headers,
                json=[],
                timeout=30,
            )
            assert_model_target_status(
                response=missing,
                status_codes=HTTPStatus.NOT_FOUND,
            )

            created = requests.post(
                url=f"{_VWS_HOST}/oauth2/clientcredentials",
                headers=headers,
                json={"scopes": []},
                timeout=30,
            )
            client_id = created.json()["client_id"]
            for content in (b"{", b'"scope"', b"[1]"):
                response = requests.put(
                    url=(
                        f"{_VWS_HOST}/oauth2/clientcredentials/"
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
    def test_client_credential_limit(
        *,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Credential creation rejects stores at their configured
        limit.
        """
        monkeypatch.setattr(
            target=_model_target_web_api,
            name="_MAX_CLIENT_CREDENTIALS",
            value=0,
        )
        with MockVWS():
            headers = {
                "Authorization": (
                    f"Bearer {TestMockOnlyOAuth2EdgeCases._management_token()}"
                ),
            }
            response = requests.post(
                url=f"{_VWS_HOST}/oauth2/clientcredentials",
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
                **_UNAUTHENTICATED_DATASET_REQUEST,
                "models": [
                    {
                        **_MODEL,
                        "stateBasedConfigurationJsonString": (
                            _STATE_CONFIGURATION
                        ),
                    },
                ],
            }
            forbidden = requests.post(
                url=f"{_VWS_HOST}/modeltargets/datasets",
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                json=state_based,
                timeout=30,
            )
            assert_model_target_status(
                response=forbidden,
                status_codes=HTTPStatus.FORBIDDEN,
            )

            invalid_view = requests.post(
                url=f"{_VWS_HOST}/modeltargets/datasets",
                headers={"Authorization": f"Bearer {_MOCK_BEARER_TOKEN}"},
                json={
                    **_UNAUTHENTICATED_DATASET_REQUEST,
                    "models": [{**_MODEL, "views": [1]}],
                },
                timeout=30,
            )
            assert_model_target_status(
                response=invalid_view,
                status_codes=HTTPStatus.BAD_REQUEST,
            )

            advanced_empty = requests.post(
                url=f"{_VWS_HOST}/modeltargets/advancedDatasets",
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
    def test_view_helper_rejects_non_objects() -> None:
        """The view validator reports view values which are not
        objects.
        """
        # pylint: disable=protected-access
        details = _model_target_web_api._view_details(  # noqa: SLF001
            models=[{"views": [1]}],
        )
        assert details == [
            {
                "code": "VALIDATION_ERROR",
                "message": "/models(0)/views(0): error.expected.jsobject",
            },
        ]

    @staticmethod
    def test_target_manager_missing_credential_delete() -> None:
        """The internal target manager returns 404 for an unknown
        credential.
        """
        response = flask_target_manager.remove_oauth2_client_credential(
            client_id="missing",
        )
        assert response.status_code == HTTPStatus.NOT_FOUND


@beartype
def _fake_response(*, status_code: HTTPStatus, text: str) -> Response:
    """Return a response for testing the status assertion helper."""
    return Response(
        text=text,
        url=f"{_VWS_HOST}/modeltargets/advancedDatasets",
        status_code=status_code,
        headers={},
        request_body=None,
        tell_position=len(text),
        content=text.encode(encoding="utf-8"),
    )


class TestAssertModelTargetStatus:
    """Tests for the Model Target status assertion helper.

    The helper exists to make real Vuforia failures legible, so its
    messages are worth testing.
    """

    @staticmethod
    @pytest.mark.parametrize(
        argnames="status_codes",
        argvalues=[
            pytest.param(HTTPStatus.OK, id="single"),
            pytest.param(
                {HTTPStatus.OK, HTTPStatus.NO_CONTENT},
                id="set",
            ),
        ],
    )
    def test_expected_status(
        *,
        status_codes: HTTPStatus | AbstractSet[HTTPStatus],
    ) -> None:
        """An expected status code does not raise."""
        response = _fake_response(status_code=HTTPStatus.OK, text="{}")
        assert_model_target_status(
            response=response,
            status_codes=status_codes,
        )

    @staticmethod
    def test_unexpected_status_shows_the_body() -> None:
        """An unexpected status code reports the URL and the body."""
        text = '{"error":{"code":"VALIDATION_ERROR"}}'
        response = _fake_response(
            status_code=HTTPStatus.BAD_REQUEST,
            text=text,
        )
        with pytest.raises(expected_exception=AssertionError) as exc:
            assert_model_target_status(
                response=response,
                status_codes=HTTPStatus.CREATED,
            )

        message = str(object=exc.value)
        assert message == (
            "Expected 201 CREATED from "
            f"{_VWS_HOST}/modeltargets/advancedDatasets, got 400.\n"
            f"\nResponse body:\n{text}"
        )

    @staticmethod
    def test_multiple_expected_statuses() -> None:
        """Every expected status code is named in the message."""
        response = _fake_response(
            status_code=HTTPStatus.BAD_REQUEST,
            text="{}",
        )
        with pytest.raises(expected_exception=AssertionError) as exc:
            assert_model_target_status(
                response=response,
                status_codes={HTTPStatus.OK, HTTPStatus.NO_CONTENT},
            )

        assert "Expected 200 OK or 204 NO_CONTENT from " in str(
            object=exc.value
        )

    @staticmethod
    def test_training_allowance_exceeded() -> None:
        """An exhausted account allowance is called out as such, in the
        first line so that a truncated CI summary still shows it.
        """
        response = _fake_response(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            text=(
                '{"error":{"code":"TRAINING_ALLOWANCE_EXCEEDED",'
                '"message":"Signing quota reached","target":"7635391"}}'
            ),
        )
        with pytest.raises(expected_exception=AssertionError) as exc:
            assert_model_target_status(
                response=response,
                status_codes=HTTPStatus.CREATED,
            )

        message = str(object=exc.value)
        first_line = message.splitlines()[0]
        assert first_line == (
            "The Vuforia account is out of Model Target training allowance - "
            "this is not a failure of the code under test."
        )
        assert "MODEL_TARGET_VUFORIA_CLIENT_ID" in message
        assert "has to be raised, or reset, on the Vuforia account" in message
