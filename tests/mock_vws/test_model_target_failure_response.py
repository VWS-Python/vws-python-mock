"""Tests for configurable Model Target failure responses."""

from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import httpx
import pytest
import requests

from mock_vws import MockVWS, ModelTargetFailureResponse, ModelTargetRequest
from tests.mock_vws.verification import UnverifiedReason, mock_only

pytestmark = mock_only(
    reason=UnverifiedReason.INHERENTLY_UNVERIFIABLE,
    detail=(
        "A configured Model Target failure response is a mock feature: real "
        "Vuforia cannot be asked to return a chosen failure shape."
    ),
)

_BASE_URL = "https://vws.vuforia.com"
_CLIENT_ID = "client-id"
_CLIENT_SECRET = "client-secret"
type _HTTPResponse = requests.Response | httpx.Response
type _DatasetRequestSender = Callable[[dict[str, Any]], _HTTPResponse]


def _dataset_body() -> dict[str, Any]:
    """Return an otherwise-valid Model Target dataset request body."""
    return {
        "name": "configured-failure-test",
        "targetSdk": "10.18",
        "models": [
            {
                "name": "model",
                "cadDataUrl": "https://example.com/model.glb",
                "views": [],
            },
        ],
    }


def _requests_create_dataset(body: dict[str, Any]) -> _HTTPResponse:
    """Acquire a token and create a dataset using ``requests``."""
    token_response = requests.post(
        url=f"{_BASE_URL}/oauth2/token",
        auth=(_CLIENT_ID, _CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    token_response.raise_for_status()
    token = token_response.json()["access_token"]
    return requests.post(
        url=f"{_BASE_URL}/modeltargets/datasets",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=30,
    )


def _httpx_create_dataset(body: dict[str, Any]) -> _HTTPResponse:
    """Acquire a token and create a dataset using ``httpx``."""
    token_response = httpx.post(
        url=f"{_BASE_URL}/oauth2/token",
        auth=(_CLIENT_ID, _CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    token_response.raise_for_status()
    token = token_response.json()["access_token"]
    return httpx.post(
        url=f"{_BASE_URL}/modeltargets/datasets",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=30,
    )


@pytest.mark.parametrize(
    argnames="send_request",
    argvalues=[_requests_create_dataset, _httpx_create_dataset],
    ids=["requests", "httpx"],
)
@pytest.mark.parametrize(
    argnames=("status_code", "headers", "body", "expected_body"),
    argvalues=[
        pytest.param(
            HTTPStatus.UNAUTHORIZED,
            {"Content-Type": "application/json"},
            '{"error":{"code":"AUTHENTICATION_ERROR","message":"No"}}',
            b'{"error":{"code":"AUTHENTICATION_ERROR","message":"No"}}',
            id="authentication-json",
        ),
        pytest.param(
            HTTPStatus.FORBIDDEN,
            {"Content-Type": "application/json"},
            '{"error":{"code":"FORBIDDEN","message":"Denied"}}',
            b'{"error":{"code":"FORBIDDEN","message":"Denied"}}',
            id="generic-json",
        ),
        pytest.param(
            HTTPStatus.CONFLICT,
            {"Content-Type": "text/plain"},
            "not json",
            b"not json",
            id="generic-non-json",
        ),
        pytest.param(
            HTTPStatus.BAD_GATEWAY,
            {"Content-Type": "application/octet-stream", "Retry-After": "5"},
            b"\xffupstream failure",
            b"\xffupstream failure",
            id="server-error",
        ),
    ],
)
def test_configured_failure_response(
    *,
    send_request: _DatasetRequestSender,
    status_code: HTTPStatus,
    headers: dict[str, str],
    body: str | bytes,
    expected_body: bytes,
) -> None:
    """Both in-process backends preserve the configured response."""
    failure = ModelTargetFailureResponse(
        status_code=status_code,
        headers=headers,
        body=body,
    )

    with MockVWS(model_target_failure_response=failure):
        response = send_request(_dataset_body())

    assert response.status_code == status_code
    assert response.content == expected_body
    for name, value in headers.items():
        assert response.headers[name] == value


@pytest.mark.parametrize(
    argnames="send_request",
    argvalues=[_requests_create_dataset, _httpx_create_dataset],
    ids=["requests", "httpx"],
)
def test_unselected_request_is_handled_normally(
    *, send_request: _DatasetRequestSender
) -> None:
    """A failure configured for another phase does not affect creation."""
    failure = ModelTargetFailureResponse(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        requests=frozenset({ModelTargetRequest.STATUS}),
    )

    with MockVWS(model_target_failure_response=failure):
        response = send_request(_dataset_body())

    assert response.status_code == HTTPStatus.CREATED


@pytest.mark.parametrize(
    argnames=("method", "path_suffix", "request_phase"),
    argvalues=[
        pytest.param("POST", "", ModelTargetRequest.CREATE, id="create"),
        pytest.param(
            "GET", "/dataset-id/status", ModelTargetRequest.STATUS, id="status"
        ),
        pytest.param(
            "GET",
            "/dataset-id/dataset",
            ModelTargetRequest.DOWNLOAD,
            id="download",
        ),
        pytest.param(
            "DELETE", "/dataset-id", ModelTargetRequest.DELETE, id="delete"
        ),
    ],
)
@pytest.mark.parametrize(
    argnames="collection",
    argvalues=["datasets", "advancedDatasets"],
    ids=["standard", "advanced"],
)
def test_selected_request_returns_failure(
    *,
    method: str,
    path_suffix: str,
    request_phase: ModelTargetRequest,
    collection: str,
) -> None:
    """Every selected request phase and route family can fail."""
    failure = ModelTargetFailureResponse(
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
        headers={"Retry-After": "10"},
        body="rate limited",
        requests=frozenset({request_phase}),
    )

    with MockVWS(model_target_failure_response=failure):
        token_response = requests.post(
            url=f"{_BASE_URL}/oauth2/token",
            auth=(_CLIENT_ID, _CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        token_response.raise_for_status()
        token = token_response.json()["access_token"]
        response = requests.request(
            method=method,
            url=f"{_BASE_URL}/modeltargets/{collection}{path_suffix}",
            headers={"Authorization": f"Bearer {token}"},
            json=_dataset_body(),
            timeout=30,
        )

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert response.headers["Retry-After"] == "10"
    assert response.text == "rate limited"
