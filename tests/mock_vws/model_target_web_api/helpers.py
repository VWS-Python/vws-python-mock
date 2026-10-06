"""Shared helpers for model target web api tests."""

import json
from http import HTTPStatus
from typing import TypedDict

import requests
from beartype import beartype
from pydantic import TypeAdapter
from vws.response import Response

from mock_vws.model_target import (
    JSONValue,
)
from tests.mock_vws.fixtures.model_target_prepared_requests import (
    credentials_for_backend,
    get_access_token,
)
from tests.mock_vws.fixtures.vuforia_backends import (
    VuforiaBackend,
)
from tests.mock_vws.utils.assertions import (
    assert_model_target_status,
)

VWS_HOST = "https://vws.vuforia.com"
MOCK_BEARER_TOKEN = (
    "eyJhbGciOiJtb2NrIn0."
    "eyJzY29wZSI6Im1vZGVsdGFyZ2V0cy5zdGFuZGFyZG1vZGVsdGFyZ2V0LmFsbCJ9."
    "c2lnbmF0dXJl"
)


class ErrorDetail(TypedDict):
    """A validation detail in a Model Target API error response."""

    code: str
    message: str


class Error(TypedDict):
    """The error object in a Model Target API response."""

    code: str
    message: str


class TargetedError(Error):
    """An API error which identifies the failed target."""

    target: str


class ValidationError(TargetedError):
    """An API validation error with field-level details."""

    details: list[ErrorDetail]


class TargetedErrorResponse(TypedDict):
    """A targeted Model Target API error response."""

    error: TargetedError


class ValidationErrorResponse(TypedDict):
    """A Model Target API validation error response."""

    error: ValidationError


@beartype
def parse_response_json(
    *,
    response: requests.Response | Response,
) -> dict[str, JSONValue]:
    """Validate and return a JSON object response."""
    return TypeAdapter(type=dict[str, JSONValue]).validate_json(response.text)


@beartype
def response_targeted_error(
    *,
    response: requests.Response | Response,
) -> TargetedError:
    """Validate and return a targeted Model Target API error response."""
    body = TypeAdapter(type=TargetedErrorResponse).validate_json(
        response.text,
    )
    return body["error"]


@beartype
def response_validation_error(
    *,
    response: requests.Response | Response,
) -> ValidationError:
    """Validate and return a Model Target API validation error
    response.
    """
    body = TypeAdapter(type=ValidationErrorResponse).validate_json(
        response.text,
    )
    return body["error"]


VIEW: dict[str, object] = {
    "name": "view-name",
    "guideViewPosition": {
        "translation": [0, 0, 5],
        "rotation": [0, 0, 0, 1],
    },
}


MODEL: dict[str, object] = {
    "name": "model-name",
    "cadDataUrl": "https://example.com/model.glb",
    "views": [VIEW],
}

UNAUTHENTICATED_DATASET_REQUEST: dict[str, object] = {
    "name": "dataset-name",
    "targetSdk": "10.18",
    "models": [MODEL],
}

STATE_CONFIGURATION = json.dumps(
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
def assert_oauth2_error(
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
def assert_model_target_error(
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
def access_token_for_backend(*, backend: VuforiaBackend) -> str:
    """Return a valid access token for the chosen backend."""
    credentials = credentials_for_backend(backend=backend)
    return get_access_token(credentials=credentials, backend=backend)
