"""Tests for concerns which apply across Model Target Web API
endpoints.

These mirror the cross-cutting tests which the ``endpoint`` fixture
supports for the VWS and Query APIs. The Model Target Web API uses
OAuth2 bearer tokens rather than HMAC signatures, so the VWS
``Authorization`` and ``Date`` header concerns do not apply to it, and
it gets its own smaller set of concerns via the
``model_target_endpoint`` fixture.
"""

import dataclasses
import json
from http import HTTPStatus

import pytest
from vws.response import Response

from tests.mock_vws.fixtures.model_target_prepared_requests import (
    MODEL_TARGET_DATASET_UUID,
    credentials_for_backend,
    get_access_token,
)
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.utils import ModelTargetEndpoint


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
    assert response.status_code == status_code
    assert json.loads(s=response.text) == {
        "error": {
            "code": code,
            "message": message,
            "target": target,
        },
    }


def _assert_unknown_dataset(*, response: Response) -> None:
    """Assert a NOT_FOUND error for the unknown dataset UUID which the
    prepared requests use.

    The body-less Model Target endpoints ignore any request body, so a
    request with a valid bearer token and an unexpected or malformed body
    reaches the dataset lookup.
    """
    assert response.status_code == HTTPStatus.NOT_FOUND
    error = json.loads(s=response.text)["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message"] == (
        "Could not find a model-view database with uuid "
        f"{MODEL_TARGET_DATASET_UUID}"
    )
    # The user-id portion is per-account in real Vuforia, so check only
    # the stable prefix.
    assert error["target"].startswith("userId:")


def _access_token_for_backend(*, backend: VuforiaBackend) -> str:
    """Return a valid access token for the chosen backend."""
    credentials = credentials_for_backend(backend=backend)
    return get_access_token(credentials=credentials, backend=backend)


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
class TestAuthorizationHeader:
    """Tests for the ``Authorization`` header on Model Target
    endpoints.
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


class TestInvalidJson:
    """Tests for giving Model Target endpoints bodies which are not
    valid JSON objects.
    """

    @staticmethod
    def test_wrong_content_type(
        *,
        verify_model_target_mock_vuforia: VuforiaBackend,
        model_target_endpoint: ModelTargetEndpoint,
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
        new_headers.pop("Content-Type", None)
        new_endpoint = dataclasses.replace(
            model_target_endpoint,
            headers=new_headers,
        )

        response = new_endpoint.send()

        if not model_target_endpoint.takes_json_body:
            _assert_unknown_dataset(response=response)
            return

        assert response.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
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

        assert response.status_code == HTTPStatus.BAD_REQUEST
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

        assert response.status_code == HTTPStatus.BAD_REQUEST
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
