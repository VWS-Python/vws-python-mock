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

import dataclasses
from http import HTTPStatus

import pytest

from vws_mock_contract_tests.model_target_web_api.assertions import (
    assert_model_target_error,
)
from vws_mock_contract_tests.utils import ModelTargetEndpoint


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
            ("Unsecured (plain) JWTs are rejected, extend class to handle"),
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
